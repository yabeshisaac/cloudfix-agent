"""
CloudFix tools.

AWS inspection tools are read-only.
They inspect S3 and IAM configuration and return evidence
to the Strands agent.
"""

import json
import urllib.parse

import boto3
from botocore.exceptions import ClientError
from strands import tool


_session = boto3.Session()


def _client(service):
    return _session.client(service)


def _safe_call(fn, **kwargs):
    """
    Execute an AWS API call safely and return:
        (response, None)
    or:
        (None, error_dictionary)
    """

    try:
        return fn(**kwargs), None

    except ClientError as exc:
        error = exc.response.get("Error", {})

        return None, {
            "code": error.get("Code", "Unknown"),
            "message": error.get("Message", str(exc)),
        }

    except Exception as exc:
        return None, {
            "code": "UnexpectedError",
            "message": str(exc),
        }


def _get_policy_document(iam, policy_arn):
    """
    Retrieve the default version document of an IAM managed policy.
    """

    metadata, err = _safe_call(
        iam.get_policy,
        PolicyArn=policy_arn,
    )

    if err or not metadata:
        return {"error": err}

    version_id = metadata["Policy"]["DefaultVersionId"]

    version, err = _safe_call(
        iam.get_policy_version,
        PolicyArn=policy_arn,
        VersionId=version_id,
    )

    if err or not version:
        return {"error": err}

    document = version["PolicyVersion"]["Document"]

    if isinstance(document, str):
        try:
            document = json.loads(
                urllib.parse.unquote(document)
            )
        except (json.JSONDecodeError, TypeError):
            pass

    return document


# =========================================================
# S3 INSPECTION
# =========================================================

@tool
def inspect_bucket(bucket_name: str) -> dict:
    """
    Inspect an S3 bucket for configuration relevant to
    access troubleshooting.

    Checks:

    - Bucket existence
    - Region
    - Block Public Access
    - Bucket policy
    - Bucket policy status
    - Server-side encryption
    - Object ownership controls

    READ-ONLY.

    Args:
        bucket_name: Name of the S3 bucket.
    """

    s3 = _client("s3")

    result = {
        "bucket_name": bucket_name
    }

    # -----------------------------------------------------
    # Bucket existence
    # -----------------------------------------------------

    _, err = _safe_call(
        s3.head_bucket,
        Bucket=bucket_name,
    )

    if err:
        result["exists"] = False
        result["head_bucket_error"] = err
        return result

    result["exists"] = True

    # -----------------------------------------------------
    # Region
    # -----------------------------------------------------

    location, err = _safe_call(
        s3.get_bucket_location,
        Bucket=bucket_name,
    )

    if err:
        result["region"] = None
        result["region_error"] = err
    else:
        result["region"] = (
            location.get("LocationConstraint")
            or "us-east-1"
        )

    # -----------------------------------------------------
    # Block Public Access
    # -----------------------------------------------------

    public_access, err = _safe_call(
        s3.get_public_access_block,
        Bucket=bucket_name,
    )

    if err:
        result["public_access_block"] = None
        result["public_access_block_error"] = err
    else:
        result["public_access_block"] = (
            public_access.get(
                "PublicAccessBlockConfiguration"
            )
        )

    # -----------------------------------------------------
    # Bucket policy
    # -----------------------------------------------------

    policy, err = _safe_call(
        s3.get_bucket_policy,
        Bucket=bucket_name,
    )

    if err:
        result["bucket_policy"] = None
        result["bucket_policy_error"] = err

    else:
        try:
            result["bucket_policy"] = json.loads(
                policy["Policy"]
            )
        except (KeyError, json.JSONDecodeError):
            result["bucket_policy"] = policy.get(
                "Policy"
            )

    # -----------------------------------------------------
    # Bucket policy status
    # -----------------------------------------------------

    policy_status, err = _safe_call(
        s3.get_bucket_policy_status,
        Bucket=bucket_name,
    )

    if err:
        result["policy_status"] = None
        result["policy_status_error"] = err
    else:
        result["policy_status"] = (
            policy_status.get("PolicyStatus")
        )

    # -----------------------------------------------------
    # Encryption
    # -----------------------------------------------------

    encryption, err = _safe_call(
        s3.get_bucket_encryption,
        Bucket=bucket_name,
    )

    if err:
        result["encryption"] = None
        result["encryption_error"] = err
    else:
        result["encryption"] = (
            encryption.get(
                "ServerSideEncryptionConfiguration"
            )
        )

    # -----------------------------------------------------
    # Object ownership
    # -----------------------------------------------------

    ownership, err = _safe_call(
        s3.get_bucket_ownership_controls,
        Bucket=bucket_name,
    )

    if err:
        result["ownership_controls"] = None
        result["ownership_controls_error"] = err
    else:
        result["ownership_controls"] = (
            ownership.get("OwnershipControls")
        )

    return result


# =========================================================
# IAM INSPECTION
# =========================================================

@tool
def inspect_iam_user(user_name: str) -> dict:
    """
    Inspect permissions associated with an IAM user.

    Checks:

    - IAM user ARN
    - Attached managed policies
    - Managed policy documents
    - Inline user policies
    - IAM group memberships
    - Group managed policies
    - Group inline policies
    - Permissions boundary
    - Permissions boundary policy document

    READ-ONLY.

    Args:
        user_name: IAM user name.
    """

    iam = _client("iam")

    result = {
        "user_name": user_name
    }

    # -----------------------------------------------------
    # IAM user
    # -----------------------------------------------------

    user_response, err = _safe_call(
        iam.get_user,
        UserName=user_name,
    )

    if err:
        result["exists"] = False
        result["get_user_error"] = err
        return result

    result["exists"] = True

    user = user_response["User"]

    result["arn"] = user.get("Arn")

    # -----------------------------------------------------
    # Permissions boundary
    # -----------------------------------------------------

    boundary = user.get("PermissionsBoundary")

    if boundary:

        boundary_arn = boundary.get(
            "PermissionsBoundaryArn"
        )

        result["permissions_boundary"] = {
            "arn": boundary_arn,
            "document": _get_policy_document(
                iam,
                boundary_arn,
            ),
        }

    else:
        result["permissions_boundary"] = None

    # -----------------------------------------------------
    # Attached user managed policies
    # -----------------------------------------------------

    attached, err = _safe_call(
        iam.list_attached_user_policies,
        UserName=user_name,
    )

    if err:
        result[
            "attached_managed_policies_error"
        ] = err

    managed_policies = []

    for policy in (
        attached or {}
    ).get("AttachedPolicies", []):

        document = _get_policy_document(
            iam,
            policy["PolicyArn"],
        )

        managed_policies.append({
            "name": policy["PolicyName"],
            "arn": policy["PolicyArn"],
            "document": document,
        })

    result[
        "attached_managed_policies"
    ] = managed_policies

    # -----------------------------------------------------
    # Inline user policies
    # -----------------------------------------------------

    inline_names, err = _safe_call(
        iam.list_user_policies,
        UserName=user_name,
    )

    if err:
        result["inline_policies_error"] = err

    inline_policies = []

    for policy_name in (
        inline_names or {}
    ).get("PolicyNames", []):

        policy, policy_err = _safe_call(
            iam.get_user_policy,
            UserName=user_name,
            PolicyName=policy_name,
        )

        if policy:
            inline_policies.append({
                "name": policy_name,
                "document": policy.get(
                    "PolicyDocument"
                ),
            })

        elif policy_err:
            inline_policies.append({
                "name": policy_name,
                "error": policy_err,
            })

    result["inline_policies"] = inline_policies

    # -----------------------------------------------------
    # IAM groups
    # -----------------------------------------------------

    groups_response, err = _safe_call(
        iam.list_groups_for_user,
        UserName=user_name,
    )

    if err:
        result["groups_error"] = err

    group_results = []

    for group in (
        groups_response or {}
    ).get("Groups", []):

        group_name = group["GroupName"]

        # Group managed policies

        group_attached, group_attached_err = (
            _safe_call(
                iam.list_attached_group_policies,
                GroupName=group_name,
            )
        )

        group_managed = []

        for policy in (
            group_attached or {}
        ).get("AttachedPolicies", []):

            document = _get_policy_document(
                iam,
                policy["PolicyArn"],
            )

            group_managed.append({
                "name": policy["PolicyName"],
                "arn": policy["PolicyArn"],
                "document": document,
            })

        # Group inline policies

        group_inline_names, group_inline_err = (
            _safe_call(
                iam.list_group_policies,
                GroupName=group_name,
            )
        )

        group_inline = []

        for policy_name in (
            group_inline_names or {}
        ).get("PolicyNames", []):

            policy, policy_err = _safe_call(
                iam.get_group_policy,
                GroupName=group_name,
                PolicyName=policy_name,
            )

            if policy:
                group_inline.append({
                    "name": policy_name,
                    "document": policy.get(
                        "PolicyDocument"
                    ),
                })

            elif policy_err:
                group_inline.append({
                    "name": policy_name,
                    "error": policy_err,
                })

        group_result = {
            "group_name": group_name,
            "attached_managed_policies":
                group_managed,
            "inline_policies":
                group_inline,
        }

        if group_attached_err:
            group_result[
                "attached_managed_policies_error"
            ] = group_attached_err

        if group_inline_err:
            group_result[
                "inline_policies_error"
            ] = group_inline_err

        group_results.append(group_result)

    result["groups"] = group_results

    return result


# =========================================================
# POLICY RECOMMENDATION
# =========================================================

@tool
def suggest_policy_fix(
    missing_actions: list[str],
    bucket_name: str,
    resource_scope: str = "auto",
) -> dict:
    """
    Generate a least-privilege example IAM policy for
    missing S3 permissions.

    IMPORTANT:

    This function ONLY generates JSON.

    It does NOT attach or modify any IAM policy.

    S3 bucket-level and object-level permissions require
    different resource ARNs.

    Example:

        s3:ListBucket
            -> arn:aws:s3:::bucket-name

        s3:GetObject
            -> arn:aws:s3:::bucket-name/*

    Args:
        missing_actions:
            Missing S3 actions.

        bucket_name:
            Name of the affected bucket.

        resource_scope:
            Retained for compatibility.
            Automatic resource mapping is preferred.
    """

    bucket_arn = (
        f"arn:aws:s3:::{bucket_name}"
    )

    object_arn = (
        f"arn:aws:s3:::{bucket_name}/*"
    )

    # Common S3 bucket-level actions.
    bucket_actions = {
        "s3:ListBucket",
        "s3:ListBucketVersions",
        "s3:GetBucketLocation",
        "s3:GetBucketPolicy",
        "s3:GetBucketAcl",
        "s3:GetBucketVersioning",
    }

    bucket_level_actions = []
    object_level_actions = []

    for action in missing_actions:

        if action in bucket_actions:
            bucket_level_actions.append(
                action
            )

        else:
            object_level_actions.append(
                action
            )

    statements = []

    # Bucket-level statement
    if bucket_level_actions:

        statements.append({
            "Sid": "CloudFixBucketPermissions",
            "Effect": "Allow",
            "Action": bucket_level_actions,
            "Resource": bucket_arn,
        })

    # Object-level statement
    if object_level_actions:

        statements.append({
            "Sid": "CloudFixObjectPermissions",
            "Effect": "Allow",
            "Action": object_level_actions,
            "Resource": object_arn,
        })

    policy = {
        "Version": "2012-10-17",
        "Statement": statements,
    }

    return {
        "suggested_policy": policy,
        "note": (
            "Least-privilege example generated by CloudFix. "
            "Review before attaching. "
            "Nothing was applied automatically."
        ),
    }
