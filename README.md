# CloudFix

AI-powered AWS S3/IAM troubleshooting agent built with the [Strands Agents
SDK](https://strandsagents.com/) + a local LLM via [Ollama](https://ollama.com) + boto3.
Describe an access problem in plain English; CloudFix inspects your actual
bucket and IAM configuration, reasons about the likely root cause, and
suggests a fix. Read-only -- it never modifies AWS resources.

Built for the AWS "Agents for Humans" Hackathon -- **Professional Agents** track.

![CloudFix Architecture](./Architecture%20Digaram.png)

## The Problem

"Why can't this user access that bucket?" is one of the most common -- and
most time-consuming -- troubleshooting tasks in AWS. The answer could be a
missing IAM action, an explicit Deny, a misconfigured bucket policy, a
permissions boundary, or any of a dozen other things. Engineers usually
resolve this by manually digging through IAM console tabs and
cross-referencing policies by hand.

CloudFix automates that investigation. It inspects the real bucket and the
real IAM user, reasons over the evidence like an experienced engineer would,
and tells you exactly what's missing -- with a ready-to-review policy fix.

## Files

- `tools.py` -- boto3-backed, read-only inspection tools (`inspect_bucket`,
  `inspect_iam_user`, `suggest_policy_fix`)
- `agent.py` -- Strands `Agent` wiring + CLI entry point
- `app.py` -- minimal Flask web UI wrapping the agent
- `cloudfix-readonly-policy.json` -- IAM policy to attach to CloudFix's own
  credentials, scoped to only what it needs
- `Architecture Digaram.png` -- architecture diagram

## How It Works

CloudFix is a Strands Agent with three read-only tools:

1. **`inspect_bucket`** -- bucket existence/region, Block Public Access,
   encryption config, bucket policy, ownership controls.
2. **`inspect_iam_user`** -- attached managed policies (with full policy
   documents), inline policies, group memberships/policies, and any
   permissions boundary.
3. **`suggest_policy_fix`** -- generates an example IAM policy JSON snippet
   scoped to the exact missing actions and bucket. Never applies anything.

The agent's system prompt walks it through a structured diagnostic
checklist: explicit Allow, explicit Deny (overrides Allow), bucket policy,
permissions boundary, and whether resource ARNs actually match the bucket
in question.

**CloudFix never modifies AWS resources.** Every tool call is a
`Get*`/`List*`/`Describe*` API. Suggested fixes are for human review, never
auto-applied.

## Tech Stack

- [Strands Agents SDK](https://strandsagents.com/) -- agent orchestration and tool-calling
- **Ollama** -- local LLM inference (no external API cost, runs fully
  offline once the model is pulled)
- **boto3** -- read-only AWS API access (S3 + IAM)
- **Flask** -- lightweight web UI

> **Why local instead of Bedrock?** Bedrock model invocation was blocked at
> the AWS account level for this project (`ValidationException: Operation
> not allowed`, reproducible even in the Bedrock console Playground with
> full admin permissions -- an account-level restriction, not a code or IAM
> issue). Strands' model-provider abstraction meant switching to Ollama
> required no changes to the agent's tools or reasoning logic, only the
> model provider in `agent.py`.

## Setup

### Prerequisites
- Python 3.11+
- [Ollama](https://ollama.com) installed and running
- AWS credentials configured (`aws configure`) with read-only S3/IAM
  permissions -- see [`cloudfix-readonly-policy.json`](./cloudfix-readonly-policy.json)

### Installation

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
pip install "strands-agents[ollama]"
```

### Pull the local model

```bash
ollama pull llama3.1
```

### AWS credentials

```bash
aws configure
```

Attach `cloudfix-readonly-policy.json` to the IAM user/role CloudFix runs
as (separate from the demo IAM user you're diagnosing -- CloudFix's own
credentials need read access to inspect things; the demo user is the one
with the intentionally-broken policy).

## Step-by-step build order

1. **Test `tools.py` standalone first:**
```bash
   python -c "from tools import inspect_bucket; import json; print(json.dumps(inspect_bucket('your-bucket-name'), indent=2, default=str))"
```
2. **Run the agent from the CLI:**
```bash
   python agent.py "Why can't test-user access my-bucket?"
```
3. **Only once step 2 works**, start the Flask UI:
```bash
   python app.py
```
   Open http://localhost:5000

## Demo scenario

1. Create bucket `cloudfix-demo-bucket` and IAM user `cloudfix-demo-user`.
2. Attach a policy to `cloudfix-demo-user` that grants `s3:ListBucket` but
   *omits* `s3:GetObject`.
3. Ask CloudFix: `Why can't cloudfix-demo-user download files from
   cloudfix-demo-bucket?`
4. Expected: CloudFix inspects both, identifies the missing `s3:GetObject`
   permission, explains it plainly, and calls `suggest_policy_fix` to
   generate the corrected policy JSON.

## What's intentionally NOT in the MVP

EC2/security groups, VPC/networking, RDS connectivity, Lambda permissions,
KMS, CloudTrail, CloudWatch logs, cross-account access.

## Safety

All tools are read-only (`Get*`/`List*`/`Describe*` boto3 calls only).
`suggest_policy_fix` only returns JSON text -- it never calls an IAM
`Put*`/`Attach*` API. Scope CloudFix's own credentials to
`cloudfix-readonly-policy.json` so this is enforced at the AWS level too,
not just in the agent's code.

## License

MIT
