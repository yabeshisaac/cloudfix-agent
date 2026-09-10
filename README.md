# CloudFix

AI-powered AWS S3/IAM troubleshooting agent built with the Strands Agents SDK
+ Amazon Bedrock (Claude) + boto3. Describe an access problem in plain
English; CloudFix inspects your actual bucket and IAM configuration, reasons
about the likely root cause, and suggests a fix. Read-only -- it never
modifies AWS resources.

## Files

- `tools.py` -- boto3-backed, read-only inspection tools (`inspect_bucket`,
  `inspect_iam_user`, `suggest_policy_fix`)
- `agent.py` -- Strands `Agent` wiring + CLI entry point (**build/test this first**)
- `app.py` -- minimal Flask web UI wrapping the agent (**wire up last**)
- `cloudfix-readonly-policy.json` -- IAM policy to attach to CloudFix's own
  credentials, scoped to only what it needs

## Setup

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### AWS credentials

You need an AWS account with Bedrock model access enabled (Claude) in a
region that supports it (e.g. `us-east-1`).

```bash
aws configure
```

Or set env vars:

```bash
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export AWS_REGION=us-east-1
```

Attach `cloudfix-readonly-policy.json` to the IAM user/role CloudFix runs
as (this is a *separate* concern from the demo IAM user you're diagnosing
-- CloudFix's own credentials need read access to inspect things; the demo
user is the one with the intentionally-broken policy).

> If you get "on-demand throughput isn't supported" from Bedrock, prefix
> the model id with `us.` (e.g. `us.anthropic.claude-sonnet-4-6`) -- see
> `agent.py`.

## Step-by-step build order (do this, in this order)

1. **Test `tools.py` standalone first**, before involving the agent at all.
   This isolates boto3/permission problems from agent/model problems:
   ```bash
   python -c "from tools import inspect_bucket; import json; print(json.dumps(inspect_bucket('your-bucket-name'), indent=2, default=str))"
   ```
   Fix any AWS permission or credential issues here before moving on.

2. **Run the agent from the CLI:**
   ```bash
   python agent.py "Why can't test-user access my-bucket?"
   ```
   Watch that it actually calls both tools (Strands prints tool calls by
   default) rather than just answering from general knowledge.

3. **Only once step 2 works**, start the Flask UI:
   ```bash
   python app.py
   ```
   Open http://localhost:5000

## Demo scenario (for your submission video)

1. Create bucket `cloudfix-demo-bucket` and IAM user `cloudfix-demo-user`.
2. Attach a policy to `cloudfix-demo-user` that grants `s3:ListBucket` but
   *omits* `s3:GetObject`.
3. Ask CloudFix: `Why can't cloudfix-demo-user download files from
   cloudfix-demo-bucket?`
4. Expected: CloudFix inspects both, identifies the missing `s3:GetObject`
   permission, explains it plainly, and calls `suggest_policy_fix` to
   generate the corrected policy JSON.

## What's intentionally NOT in the MVP

Per the original spec -- do not build these until S3+IAM works end to end:
EC2/security groups, VPC/networking, RDS connectivity, Lambda permissions,
KMS, CloudTrail, CloudWatch logs, cross-account access.

## Safety

All tools are read-only (`Get*`/`List*`/`Describe*` boto3 calls only).
`suggest_policy_fix` only returns JSON text -- it never calls an IAM
`Put*`/`Attach*` API. Scope CloudFix's own credentials to
`cloudfix-readonly-policy.json` so this is enforced at the AWS level too,
not just in the agent's code.
