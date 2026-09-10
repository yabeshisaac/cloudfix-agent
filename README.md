# CloudFix

An AI agent that diagnoses AWS S3 and IAM access problems by inspecting your actual AWS configuration — not generic advice, real evidence.

Built for the AWS "Agents for Humans" Hackathon — **Professional Agents** track.

## The Problem

"Why can't this user access that bucket?" is one of the most common — and most time-consuming — troubleshooting tasks in AWS. The answer could be a missing IAM action, an explicit Deny, a misconfigured bucket policy, a permissions boundary, or a dozen other things. Engineers usually resolve this by manually digging through IAM console tabs, cross-referencing policies by hand.

CloudFix automates that investigation. It's a read-only AWS troubleshooting agent: describe the problem in plain English, and it inspects the real bucket and the real IAM user, reasons over the evidence, and tells you exactly what's missing — with a ready-to-review policy fix.

**Who it's for:** developers, DevOps engineers, and cloud support staff who spend recurring time on AWS permission debugging — the exact kind of repetitive, judgment-heavy task the Professional Agents track calls out.

**Why it matters:** IAM misconfigurations are one of the most common causes of both "why is this broken" tickets and, on the flip side, accidental over-permissioning. A tool that explains *root cause* rather than just symptoms saves real engineering time and reduces the temptation to "just grant more access" as a quick fix.

## How It Works

CloudFix is a [Strands Agents SDK](https://github.com/strands-agents/harness-sdk) agent with three read-only tools:

1. **`inspect_bucket`** — pulls bucket existence/region, Block Public Access settings, encryption config, bucket policy, and ownership controls.
2. **`inspect_iam_user`** — pulls the user's attached managed policies (with full policy documents), inline policies, group memberships, group policies, and any permissions boundary.
3. **`suggest_policy_fix`** — generates an example IAM policy JSON snippet scoped to the exact missing actions and bucket. Never applies anything automatically.

The agent's system prompt walks it through a structured diagnostic process: check for explicit Allow, check for explicit Deny (which overrides Allow), check the bucket policy, check permissions boundaries, and verify resource ARNs actually match the bucket in question — the same mental checklist an experienced engineer would use.

**CloudFix never modifies AWS resources.** Every tool call is a `Get*`/`List*`/`Describe*` API — nothing destructive, nothing that changes state. Suggested policy fixes are presented for human review, never auto-applied.

## Architecture

┌─────────────┐ ┌──────────────┐ ┌─────────────────┐
│ User asks │────▶│ Strands Agent│────▶│ Local LLM │
│ a question │ │ (agent.py) │ │ (Ollama/qwen2.5)│
└─────────────┘ └──────┬───────┘ └─────────────────┘
│
▼
┌──────────────────────┐
│ Tools (tools.py) │
│ - inspect_bucket │
│ - inspect_iam_user │
│ - suggest_policy_fix │
└──────────┬─────────────┘
│ boto3 (read-only)
▼
┌──────────────────────┐
│ Real AWS Account │
│ (S3 + IAM APIs) │
└──────────────────────┘


Two front ends are available:
- **CLI** (`agent.py`) — single-question mode or interactive loop
- **Web UI** (`app.py`) — minimal Flask interface for a browser-based demo

## Tech Stack

- [Strands Agents SDK](https://github.com/strands-agents/harness-sdk) — agent orchestration and tool-calling
- **Ollama + Qwen2.5:7b** — local LLM inference (no external API dependency; runs fully offline once models are pulled)
- **boto3** — read-only AWS API access (S3 + IAM)
- **Flask** — lightweight web UI

## Setup

### Prerequisites
- Python 3.11+
- [Ollama](https://ollama.com) installed and running
- AWS credentials configured (`aws configure` or environment variables) with read-only S3/IAM permissions — see [`cloudfix-readonly-policy.json`](./cloudfix-readonly-policy.json) for the minimum required policy

### Installation

```bash
git clone https://github.com/yabeshisaac/cloudfix-agent.git
cd cloudfix-agent
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux
pip install -r requirements.txt
```

### Pull the local model

```bash
ollama pull qwen2.5:7b
```

### Run

**CLI (single question):**
```bash
python agent.py "Why can't test-user access my-bucket?"
```

**CLI (interactive):**
```bash
python agent.py
```

**Web UI:**
```bash
python app.py
```
Then open `http://localhost:5000`

## Required AWS Permissions

CloudFix itself needs read-only access to inspect S3 and IAM. See [`cloudfix-readonly-policy.json`](./cloudfix-readonly-policy.json) for the exact policy to attach to whatever IAM identity runs CloudFix.

## Example

$ python agent.py "Why can't cloudfix-demo-user access cloudfix-demo-bucket-yabesh?"

Tool #1: inspect_bucket
Tool #2: inspect_iam_user

Based on the evidence gathered:

The bucket exists with Block Public Access enabled and no bucket policy.
The user has an inline policy granting s3:ListBucket but NOT s3:GetObject.

Root cause: missing s3:GetObject permission on the bucket's object ARNs.

Suggested fix:
{
"Version": "2012-10-17",
"Statement": [{
"Effect": "Allow",
"Action": ["s3:GetObject"],
"Resource": "arn:aws:s3:::cloudfix-demo-bucket-yabesh/*"
}]
}


## Design Principles

- **Evidence-based, not generic**: every diagnosis is backed by actual API responses, never assumptions.
- **Read-only by design**: CloudFix can investigate but never modify — all fixes are suggestions for human review.
- **Runs locally**: using Ollama means no per-query API cost and no dependency on an external LLM provider once set up.

## License

MIT — see [LICENSE](./LICENSE)
