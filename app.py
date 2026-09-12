"""
CloudFix Web Interface

Run:
    python app.py

Open:
    http://127.0.0.1:5000
"""

import re
import threading

from flask import Flask, render_template_string, request
import markdown as md
from agent import build_agent


app = Flask(__name__)

# Build the Strands agent once when Flask starts.
agent = build_agent()

# Only one diagnosis runs at a time. A lock (not a fresh agent per
# request) avoids Strands' internal event-loop teardown/rebuild issues
# while still preventing "Agent is already processing a request" crashes.
agent_lock = threading.Lock()


# =========================================================
# Output cleanup
# =========================================================
#
# The local model (Qwen 7B) sometimes narrates a fake tool call after
# the real recommended policy -- and the exact shape of that fake text
# varies run to run, so pattern-matching specific fake-text shapes is
# not reliable long-term.
#
# Instead: truncate the response structurally, right after the first
# JSON code block that follows "RECOMMENDED FIX". CloudFix's own format
# (EVIDENCE / ROOT CAUSE / RECOMMENDED FIX + one policy block) is fixed
# by the system prompt, so anything after that policy block is discarded
# unconditionally -- regardless of what it says.

def truncate_after_recommended_fix(text: str) -> str:

    marker = re.search(r"RECOMMENDED FIX", text, re.IGNORECASE)

    if not marker:
        return text.strip()

    after_marker = text[marker.start():]

    code_block = re.search(r"```.*?```", after_marker, re.DOTALL)

    if not code_block:
        return text.strip()

    cutoff = marker.start() + code_block.end()

    return text[:cutoff].strip()


PAGE = """
<!DOCTYPE html>
<html lang="en">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">

    <title>CloudFix</title>

    <style>

        * {
            box-sizing: border-box;
        }

        body {
            margin: 0;
            background: #ffffff;
            color: #202123;
            font-family:
                -apple-system,
                BlinkMacSystemFont,
                "Segoe UI",
                Arial,
                sans-serif;
        }

        .container {
            width: 92%;
            max-width: 820px;
            margin: 0 auto;
        }


        /* HEADER */

        header {
            height: 64px;
            border-bottom: 1px solid #e5e5e5;

            display: flex;
            align-items: center;
        }

        .header-content {
            width: 92%;
            max-width: 1100px;
            margin: auto;

            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .logo {
            font-size: 21px;
            font-weight: 650;
        }

        .status {
            font-size: 12px;
            color: #6b7280;
        }


        /* HERO */

        .hero {
            text-align: center;
            padding: 75px 20px 45px;
        }

        .hero h1 {
            font-size: 36px;
            margin: 0 0 14px;
            letter-spacing: -0.5px;
        }

        .hero p {
            margin: auto;
            max-width: 620px;

            color: #6b7280;
            font-size: 16px;
            line-height: 1.6;
        }

        .hero .timing-note {
            margin: 10px auto 0;
            max-width: 620px;

            color: #9ca3af;
            font-size: 13px;
        }


        /* INPUT */

        .input-card {
            border: 1px solid #d9d9d9;
            border-radius: 16px;
            padding: 14px;

            background: #ffffff;

            box-shadow:
                0 2px 8px rgba(0, 0, 0, 0.05);
        }

        textarea {
            width: 100%;
            min-height: 105px;

            border: none;
            outline: none;
            resize: vertical;

            padding: 7px;

            background: transparent;
            color: #202123;

            font-family: inherit;
            font-size: 16px;
            line-height: 1.5;
        }

        textarea::placeholder {
            color: #9ca3af;
        }


        /* BUTTON AREA */

        .actions {
            display: flex;
            justify-content: flex-end;
            margin-top: 8px;
        }

        button {
            border: none;
            border-radius: 9px;

            background: #202123;
            color: white;

            padding: 10px 18px;

            font-size: 14px;
            font-weight: 600;

            cursor: pointer;
        }

        button:hover {
            background: #343541;
        }

        button:disabled {
            opacity: 0.6;
            cursor: not-allowed;
        }


        /* LOADING */

        .loading {
            display: none;

            margin-top: 20px;
            padding: 16px 18px;

            border: 1px solid #e5e5e5;
            border-radius: 12px;

            color: #555;
            font-size: 14px;

            background: #fafafa;
        }

        .loading .loading-sub {
            margin-top: 6px;
            margin-left: 23px;

            color: #9ca3af;
            font-size: 12.5px;
        }

        .spinner {
            display: inline-block;

            width: 14px;
            height: 14px;

            margin-right: 9px;

            border: 2px solid #ddd;
            border-top-color: #202123;
            border-radius: 50%;

            vertical-align: -2px;

            animation: spin 0.8s linear infinite;
        }

        @keyframes spin {
            to {
                transform: rotate(360deg);
            }
        }


        /* RESULT */

        .result {
            margin-top: 35px;
        }

        .result-header {
            font-size: 15px;
            font-weight: 650;

            margin-bottom: 12px;
        }

        /* Rendered markdown diagnosis output */

        .markdown-body {
            background: #f7f7f8;
            border: 1px solid #e5e5e5;
            border-radius: 12px;
            padding: 22px 26px;

            color: #292929;
            font-size: 14.5px;
            line-height: 1.7;
        }

        .markdown-body h1,
        .markdown-body h2,
        .markdown-body h3 {
            margin: 18px 0 8px;
            font-size: 16px;
            font-weight: 700;
            letter-spacing: 0.3px;
            color: #111827;
        }

        .markdown-body h1:first-child,
        .markdown-body h2:first-child,
        .markdown-body h3:first-child {
            margin-top: 0;
        }

        .markdown-body p {
            margin: 8px 0;
        }

        .markdown-body ul,
        .markdown-body ol {
            margin: 8px 0;
            padding-left: 22px;
        }

        .markdown-body li {
            margin: 4px 0;
        }

        .markdown-body strong {
            color: #111827;
            font-weight: 700;
        }

        .markdown-body code {
            background: #ececee;
            border-radius: 4px;
            padding: 1px 5px;
            font-family: Consolas, "Courier New", monospace;
            font-size: 13px;
        }

        .markdown-body pre {
            background: #1e1e1e;
            color: #e5e5e5;
            border-radius: 10px;
            padding: 16px;
            overflow-x: auto;
            margin: 10px 0;
        }

        .markdown-body pre code {
            background: none;
            color: inherit;
            padding: 0;
            font-size: 13px;
        }

        .error {
            background: #fff7f7;
            border-color: #efcaca;
        }


        /* INFO */

        .info {
            display: flex;
            justify-content: center;
            gap: 24px;

            margin: 32px 0 70px;

            color: #8a8a8a;
            font-size: 12px;
        }


        /* FOOTER */

        footer {
            text-align: center;

            border-top: 1px solid #eeeeee;

            padding: 22px;

            color: #999;
            font-size: 12px;
        }


        @media (max-width: 650px) {

            .hero {
                padding-top: 50px;
            }

            .hero h1 {
                font-size: 29px;
            }

            .info {
                flex-direction: column;
                align-items: center;
                gap: 8px;
            }
        }

    </style>

</head>


<body>


<header>

    <div class="header-content">

        <div class="logo">
            CloudFix
        </div>

        <div class="status">
            Read-only AWS troubleshooting
        </div>

    </div>

</header>


<main class="container">


    <section class="hero">

        <h1>
            How can CloudFix help?
        </h1>

        <p>
            Describe an Amazon S3 or IAM access problem.
            CloudFix will inspect your actual AWS configuration,
            identify the likely root cause, and recommend a
            least-privilege fix.
        </p>

        <p class="timing-note">
            Runs on a local AI model — diagnosis may take up to 3 minutes.
        </p>

    </section>


    <form
        method="POST"
        id="diagnosisForm"
        class="input-card"
    >

        <textarea
            name="question"
            required
            placeholder="Why can't cloudfix-demo-user download files from cloudfix-demo-bucket-yabesh?"
        >{{ question or '' }}</textarea>


        <div class="actions">

            <button
                type="submit"
                id="diagnoseButton"
            >
                Diagnose
            </button>

        </div>

    </form>


    <div
        class="loading"
        id="loadingMessage"
    >

        <span class="spinner"></span>

        CloudFix is inspecting your AWS environment...

        <div class="loading-sub">
            This may take up to 3 minutes — please don't refresh or click Diagnose again.
        </div>

    </div>


    {% if answer %}

    <section class="result">

        <div class="result-header">
            CloudFix Diagnosis
        </div>

        <div class="markdown-body">{{ answer|safe }}</div>

    </section>

    {% endif %}


    {% if error %}

    <section class="result">

        <div class="result-header">
            CloudFix encountered an error
        </div>

        <pre class="error">{{ error }}</pre>

    </section>

    {% endif %}


    <div class="info">

        <span>Strands Agents SDK</span>

        <span>Real AWS evidence</span>

        <span>Human-reviewed fixes</span>

    </div>


</main>


<footer>
    CloudFix · AWS S3 & IAM Troubleshooting Agent
</footer>


<script>

    const form =
        document.getElementById("diagnosisForm");

    const button =
        document.getElementById("diagnoseButton");

    const loading =
        document.getElementById("loadingMessage");


    form.addEventListener(
        "submit",
        function () {

            button.disabled = true;

            button.textContent =
                "Diagnosing...";

            loading.style.display =
                "block";
        }
    );

</script>


</body>

</html>
"""


@app.route("/", methods=["GET", "POST"])
def index():

    answer = None
    error = None
    question = ""

    if request.method == "POST":

        question = request.form.get(
            "question",
            ""
        ).strip()

        if question:

            if not agent_lock.acquire(blocking=False):

                error = (
                    "CloudFix is still working on a previous request. "
                    "Please wait for it to finish before trying again."
                )

            else:

                try:

                    result = agent(question)

                    cleaned = truncate_after_recommended_fix(
                        str(result)
                    )

                    answer = md.markdown(
                        cleaned,
                        extensions=["fenced_code"],
                    )

                except Exception as exc:

                    error = str(exc)

                finally:

                    agent_lock.release()

    return render_template_string(
        PAGE,
        answer=answer,
        error=error,
        question=question,
    )


if __name__ == "__main__":

    print()
    print("CloudFix Web Interface")
    print("Open http://127.0.0.1:5000")
    print()

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False,
    )
