"""
CloudFix tools.

Each function is decorated with @tool so the Strands agent can call it
autonomously. Every tool is READ-ONLY -- none of these ever create, modify,
or delete an AWS resource. They only call Get*/List*/Describe* APIs.

All tools return plain dicts (never raise), with an "error" key set when a
call fails, so the agent's reasoning loop can see *why* something failed
(e.g. AccessDenied, NoSuchEntity) and factor that into its diagnosis.
"""

import json
import urllib.parse

import boto3
from botocore.exceptions import ClientError
from strands import tool

# A single boto3 session is reused across tools. boto3 will resolve
# credentials the normal way (env vars, ~/.aws/credentials, profile, etc).
_session = boto3.Session()


def _client(service):
    return _session.client(service)


def _safe_call(fn, **kwargs):
    """Call a boto3 method, returning (result, error_dict_or_None)."""
    try:
        return fn(**kwargs), None
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "Unknown")
        msg = e.response.get("Error", {}).get("Message", str(e))
        return None, {"code": code, "message": msg}
    except Exception as e:  # noqa: BLE001 - surface anything unexpected too
        return None, {"code": "UnexpectedError", "message": str(e)}


@tool
def inspect_bucket(bucket_name: str) -> dict:
    """
    Inspect an S3 bucket's configuration relevant to access troubleshooting.

    Returns bucket existence/region, Block Public Access settings,
    server-side encryption config, bucket policy (if any), bucket policy
    status (public or not), and ownership controls. Read-only.

    Args:
        bucket_name: Name of the S3 bucket to inspect.
    """
    s3 = _client("s3")
    result = {"bucket_name": bucket_name}

    # Existence + region
    _, err = _safe_call(s3.head_bucket, Bucket=bucket_name)
    if err:
        result["exists"] = False
        result["head_bucket_error"] = err
        return result
    result["exists"] = True

    loc, err = _safe_call(s3.get_bucket_location, Bucket=bucket_name)
    result["region"] = (loc or {}).get("LocationConstraint") or "us-east-1"

    # Block Public Access
    pab, err = _safe_call(s3.get_public_access_block, Bucket=bucket_name)
    if err:
        result["public_access_block"] = None
        result["public_access_block_error"] = err
    else:
        result["public_access_block"] = pab.get("PublicAccessBlockConfiguration")

    # Bucket policy
    policy, err = _safe_call(s3.get_bucket_policy, Bucket=bucket_name)
    if err:
        result["bucket_policy"] = None
        result["bucket_policy_error"] = err  # NoSuchBucketPolicy is normal/expected
    else:
        try:
            result["bucket_policy"] = json.loads(policy["Policy"])
        except (KeyError, json.JSONDecodeError):
            result["bucket_policy"] = policy.get("Policy")

    # Policy status (is the bucket considered "public" by AWS's own analysis?)
    status, err = _safe_call(s3.get_bucket_policy_status, Bucket=bucket_name)
    if err:
        result["policy_status"] = None
    else:
        result["policy_status"] = status.get("PolicyStatus")

    # Encryption
    enc, err = _safe_call(s3.get_bucket_encryption, Bucket=bucket_name)
    if err:
        result["encryption"] = None
        result["encryption_error"] = err
    else:
        result["encryption"] = enc.get("ServerSideEncryptionConfiguration")

    # Ownership controls
    own, err = _safe_call(s3.get_bucket_ownership_controls, Bucket=bucket_name)
    if err:
        result["ownership_controls"] = None
    else:
        result["ownership_controls"] = own.get("OwnershipControls")

    return result


@tool
def inspect_iam_user(user_name: str) -> dict:
    """
    Inspect an IAM user's permissions: attached managed policies (with their
    policy documents), inline policies, group memberships and group
    policies, and any permissions boundary. Read-only.

    Args:
        user_name: Name of the IAM user to inspect.
    """
    iam = _client("iam")
    result = {"user_name": user_name}

    user, err = _safe_call(iam.get_user, UserName=user_name)
    if err:
        result["exists"] = False
        result["get_user_error"] = err
        return result
    result["exists"] = True
    u = user["User"]
    result["arn"] = u.get("Arn")
    boundary = u.get("PermissionsBoundary")
    result["permissions_boundary"] = boundary.get("PermissionsBoundaryArn") if boundary else None

    # Attached managed policies (+ their documents)
    attached, err = _safe_call(iam.list_attached_user_policies, UserName=user_name)
    managed_policies = []
    for p in (attached or {}).get("AttachedPolicies", []):
        doc = _get_policy_document(iam, p["PolicyArn"])
        managed_policies.append({"name": p["PolicyName"], "arn": p["PolicyArn"], "document": doc})
    result["attached_managed_policies"] = managed_policies

    # Inline policies on the user
    inline_names, err = _safe_call(iam.list_user_policies, UserName=user_name)
    inline_policies = []
    for name in (inline_names or {}).get("PolicyNames", []):
        pol, err = _safe_call(iam.get_user_policy, UserName=user_name, PolicyName=name)
        if pol:
            inline_policies.append({"name": name, "document": pol.get("PolicyDocument")})
    result["inline_policies"] = inline_policies

    # Group memberships
    groups, err = _safe_call(iam.list_groups_for_user, UserName=user_name)
    group_results = []
    for g in (groups or {}).get("Groups", []):
        gname = g["GroupName"]
        g_attached, _ = _safe_call(iam.list_attached_group_policies, GroupName=gname)
        g_managed = []
        for p in (g_attached or {}).get("AttachedPolicies", []):
            doc = _get_policy_document(iam, p["PolicyArn"])
            g_managed.append({"name": p["PolicyName"], "arn": p["PolicyArn"], "document": doc})

        g_inline_names, _ = _safe_call(iam.list_group_policies, GroupName=gname)
        g_inline = []
        for name in (g_inline_names or {}).get("PolicyNames", []):
            pol, _ = _safe_call(iam.get_group_policy, GroupName=gname, PolicyName=name)
            if pol:
                g_inline.append({"name": name, "document": pol.get("PolicyDocument")})

        group_results.append({
            "group_name": gname,
            "attached_managed_policies": g_managed,
            "inline_policies": g_inline,
        })
    result["groups"] = group_results

    return result


def _get_policy_document(iam, policy_arn: str):
    """Fetch the default version's JSON document for a managed policy ARN."""
    meta, err = _safe_call(iam.get_policy, PolicyArn=policy_arn)
    if err or not meta:
        return {"error": err}
    version_id = meta["Policy"]["DefaultVersionId"]
    ver, err = _safe_call(iam.get_policy_version, PolicyArn=policy_arn, VersionId=version_id)
    if err or not ver:
        return {"error": err}
    doc = ver["PolicyVersion"]["Document"]
    if isinstance(doc, str):
        try:
            doc = json.loads(urllib.parse.unquote(doc))
        except json.JSONDecodeError:
            pass
    return doc


@tool
def suggest_policy_fix(missing_actions: list, bucket_name: str, resource_scope: str = "object_and_bucket") -> dict:
    """
    Generate an example IAM policy JSON snippet that grants the given S3
    actions on the given bucket. This does NOT apply anything to AWS --
    it only returns text for the user to review and apply themselves.

    Args:
        missing_actions: List of S3 actions to grant, e.g. ["s3:GetObject"].
        bucket_name: The bucket the policy should scope access to.
        resource_scope: "object_and_bucket" (default) includes both the
            bucket ARN and bucket/* object ARN; "bucket_only" or
            "object_only" restrict to just one.
    """
    bucket_arn = f"arn:aws:s3:::{bucket_name}"
    object_arn = f"arn:aws:s3:::{bucket_name}/*"

    if resource_scope == "bucket_only":
        resources = [bucket_arn]
    elif resource_scope == "object_only":
        resources = [object_arn]
    else:
        resources = [bucket_arn, object_arn]

    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "CloudFixSuggestedFix",
                "Effect": "Allow",
                "Action": missing_actions,
                "Resource": resources,
            }
        ],
    }
    return {"suggested_policy": policy, "note": "Review before attaching. This is not applied automatically."}
