# CloudFix

CloudFix is an AI-powered, read-only AWS S3/IAM troubleshooting agent built with the [Strands Agents SDK](https://strandsagents.com/), a local LLM through [Ollama](https://ollama.com), and boto3.

Describe an AWS access problem in plain English, and CloudFix inspects the actual AWS configuration, analyzes the evidence, identifies the likely root cause, and recommends a least-privilege fix.

CloudFix never modifies AWS resources. All recommended changes are presented for human review.

Built for the AWS **Agents for Humans Hackathon** — **Professional Agents** track.

![CloudFix Architecture](./Architecture%20Digaram.png)

## The Problem

AWS S3 and IAM access issues can be surprisingly time-consuming to troubleshoot.

A simple question such as:

> Why can't this IAM user download files from this S3 bucket?

may require manually checking:

- IAM inline policies
- Attached managed policies
- IAM group policies
- Permissions boundaries
- S3 bucket policies
- S3 resource ARNs
- Block Public Access settings
- Encryption configuration

CloudFix automates this investigation.

Instead of manually navigating multiple AWS console pages and comparing policies, an engineer can describe the problem in plain English and let CloudFix inspect the relevant AWS configuration.

CloudFix then returns a structured diagnosis:

**Evidence → Root Cause → Recommended Fix**

## How It Works

```text
User
  ↓
Flask Web UI
  ↓
Strands Agents SDK
  ↓
Local LLM (Ollama / Qwen2.5:7b)
  ↓
CloudFix inspection tools
  ↓
boto3 read-only AWS APIs
  ↓
Amazon S3 + AWS IAM

Response:
Evidence → Root Cause → Recommended Fix
```

CloudFix uses the Strands Agents SDK to reason about the user's request and inspect the relevant AWS configuration.

The current MVP focuses specifically on **Amazon S3 and AWS IAM access troubleshooting**.

## CloudFix Capabilities

### S3 Inspection

CloudFix can inspect:

- Bucket existence and Region
- S3 Block Public Access configuration
- Bucket policy
- Server-side encryption configuration
- Ownership controls

### IAM Inspection

CloudFix can inspect:

- IAM user information
- Attached managed policies
- Managed policy documents
- Inline policies
- IAM group memberships
- Group policies
- Permissions boundaries

### Policy Recommendation

After analyzing the evidence, CloudFix can recommend a least-privilege IAM policy for the missing S3 permissions.

The recommendation is only displayed to the user.

**CloudFix never applies the policy automatically.**

## Diagnostic Reasoning

CloudFix evaluates several common causes of S3 access failures, including:

- Missing IAM Allow permissions
- Explicit Deny statements
- Incorrect S3 resource ARNs
- Bucket policy restrictions
- Permissions boundaries
- S3 Block Public Access when relevant
- Encryption configuration when relevant

For example:

Bucket-level actions such as:

```text
s3:ListBucket
```

normally use:

```text
arn:aws:s3:::bucket-name
```

Object-level actions such as:

```text
s3:GetObject
s3:PutObject
s3:DeleteObject
```

normally use:

```text
arn:aws:s3:::bucket-name/*
```

This allows CloudFix to detect situations where the correct action exists but is scoped to the wrong AWS resource.

## Example Demo

The included demo intentionally creates an IAM permission problem.

The IAM user:

```text
cloudfix-demo-user
```

has permission to list the demo S3 bucket:

```text
s3:ListBucket
```

but does not have:

```text
s3:GetObject
```

The user asks CloudFix:

```text
Why can't cloudfix-demo-user download files from cloudfix-demo-bucket-yabesh?
```

CloudFix inspects the real IAM user and S3 bucket through boto3.

It then returns:

### EVIDENCE

The relevant IAM policies, permissions boundary information, and S3 bucket configuration discovered from AWS.

### ROOT CAUSE

The IAM user can list the bucket but does not have the required `s3:GetObject` permission for objects in the bucket.

### RECOMMENDED FIX

A least-privilege IAM policy granting the required object-level permission for the specific S3 bucket.

The recommendation is shown for human review and is never automatically applied.

## Safety

CloudFix is intentionally **read-only**.

It does not:

- Create AWS resources
- Delete AWS resources
- Modify AWS resources
- Attach IAM policies
- Modify IAM policies
- Change S3 bucket policies
- Change permissions
- Automatically apply recommended fixes

AWS inspection is performed using read-only API operations such as:

```text
Get*
List*
Describe*
```

Policy recommendations are generated as text/JSON for human review.

CloudFix's own AWS credentials can also be restricted using:

```text
cloudfix-readonly-policy.json
```

This provides an additional AWS-level safety boundary.

## Tech Stack

- **Strands Agents SDK 1.55.1** — agent orchestration and tool use
- **Ollama 0.34.0** — local LLM runtime
- **Qwen2.5:7b** — local reasoning model
- **boto3 1.43.91** — AWS SDK for Python
- **Flask** — lightweight web interface
- **Python 3.13.15**

## Project Files

```text
cloudfix-agent/
│
├── agent.py
├── app.py
├── tools.py
├── cloudfix-readonly-policy.json
├── requirements.txt
├── Architecture Digaram.png
├── README.md
└── LICENSE
```

### `agent.py`

Contains the Strands Agent configuration, local Ollama model configuration, system prompt, diagnostic reasoning instructions, and CLI interface.

### `tools.py`

Contains the boto3-backed AWS inspection functionality for Amazon S3 and AWS IAM, together with policy recommendation support.

### `app.py`

Provides the Flask web interface used to submit troubleshooting questions and display CloudFix diagnoses.

### `cloudfix-readonly-policy.json`

Example IAM policy for restricting CloudFix's AWS credentials to the read-only permissions required for inspection.

## Setup

### Prerequisites

Install:

- Python 3.11+
- Ollama
- AWS CLI / configured AWS credentials

Clone the repository and open the project directory.

### Create a virtual environment

```bash
python -m venv venv
```

Windows:

```bash
venv\Scripts\activate
```

Linux/macOS:

```bash
source venv/bin/activate
```

### Install dependencies

```bash
pip install -r requirements.txt
pip install "strands-agents[ollama]"
```

### Pull the model

```bash
ollama pull qwen2.5:7b
```

Verify:

```bash
ollama list
```

### Configure AWS credentials

```bash
aws configure
```

CloudFix should run using AWS credentials with only the read permissions required to inspect S3 and IAM.

See:

```text
cloudfix-readonly-policy.json
```

The credentials used by CloudFix are separate from the IAM user being diagnosed in the demo.

## Run CloudFix

### CLI

```bash
python agent.py
```

Or provide a question directly:

```bash
python agent.py "Why can't cloudfix-demo-user download files from cloudfix-demo-bucket-yabesh?"
```

### Web Interface

Start Flask:

```bash
python app.py
```

Then open:

```text
http://127.0.0.1:5000
```

Enter an S3/IAM access problem and select **Diagnose**.

CloudFix will inspect the relevant AWS configuration and return its diagnosis.

## Why a Local Model?

CloudFix currently uses Ollama with `qwen2.5:7b`.

During development, Amazon Bedrock model invocation was unavailable for the AWS account used for the project. Because Strands Agents supports different model providers, CloudFix could continue using the same agent architecture and AWS inspection workflow while using a local model.

The model provider is therefore separate from CloudFix's AWS inspection tools and diagnostic workflow.

## Current MVP Scope

CloudFix currently focuses on:

- Amazon S3
- AWS IAM
- S3/IAM access troubleshooting
- Evidence-based diagnosis
- Least-privilege policy recommendations
- Human-reviewed remediation

The following are intentionally outside the current MVP:

- EC2 security groups
- VPC networking
- RDS connectivity
- Lambda permissions
- Cross-account troubleshooting
- CloudTrail analysis
- CloudWatch log analysis
- Automatic remediation

These would be natural areas for future expansion.

## Hackathon Track

**AWS Agents for Humans Hackathon**

Track:

**Professional Agents**

CloudFix is designed for cloud engineers, developers, DevOps engineers, and other AWS users who repeatedly troubleshoot access and permissions problems.

The goal is to turn a repetitive, judgment-heavy troubleshooting workflow into a simple question while keeping the final remediation under human control.

## License

MIT
