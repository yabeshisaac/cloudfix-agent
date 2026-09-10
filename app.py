"""
CloudFix Web UI

Run:
    python app.py

Then open:
    http://localhost:5000
"""

from flask import Flask, render_template_string, request

from agent import build_agent


app = Flask(__name__)

# Build the Strands agent once when the application starts.
agent = build_agent()


PAGE = """
<!doctype html>

<html lang="en">

<head>

<meta charset="utf-8">

<meta name="viewport" content="width=device-width, initial-scale=1">

<title>CloudFix — AWS Troubleshooting Agent</title>

<style>

* {
    box-sizing: border-box;
}

body {

    margin: 0;

    font-family:
        Inter,
        -apple-system,
        BlinkMacSystemFont,
        "Segoe UI",
        sans-serif;

    background: #0d1117;

    color: #e6edf3;
}


/* --------------------------------------------------
   Header
-------------------------------------------------- */

header {

    border-bottom: 1px solid #21262d;

    background: #161b22;

    padding: 18px 0;
}

.header-content {

    max-width: 900px;

    margin: auto;

    padding: 0 24px;

    display: flex;

    align-items: center;

    justify-content: space-between;
}

.logo {

    font-size: 24px;

    font-weight: 700;

    letter-spacing: -0.5px;
}

.logo span {

    color: #58a6ff;
}

.badge {

    background: #1f6feb22;

    color: #58a6ff;

    border: 1px solid #1f6feb;

    padding: 5px 10px;

    border-radius: 20px;

    font-size: 12px;
}


/* --------------------------------------------------
   Main container
-------------------------------------------------- */

.container {

    max-width: 900px;

    margin: 55px auto;

    padding: 0 24px;
}


/* --------------------------------------------------
   Hero
-------------------------------------------------- */

.hero {

    text-align: center;

    margin-bottom: 40px;
}

.hero h1 {

    font-size: 38px;

    margin-bottom: 10px;
}

.hero p {

    color: #8b949e;

    font-size: 17px;

    line-height: 1.6;

    max-width: 650px;

    margin: auto;
}


/* --------------------------------------------------
   Main card
-------------------------------------------------- */

.card {

    background: #161b22;

    border: 1px solid #30363d;

    border-radius: 12px;

    padding: 26px;

    box-shadow: 0 10px 30px rgba(0,0,0,.25);
}

.label {

    font-size: 14px;

    font-weight: 600;

    margin-bottom: 10px;

    display: block;
}


/* --------------------------------------------------
   Input
-------------------------------------------------- */

textarea {

    width: 100%;

    resize: vertical;

    min-height: 110px;

    padding: 15px;

    font-family: inherit;

    font-size: 15px;

    line-height: 1.5;

    background: #0d1117;

    color: #e6edf3;

    border: 1px solid #30363d;

    border-radius: 8px;

    outline: none;
}

textarea:focus {

    border-color: #58a6ff;

    box-shadow: 0 0 0 3px rgba(88,166,255,.12);
}


/* --------------------------------------------------
   Button
-------------------------------------------------- */

button {

    width: 100%;

    margin-top: 14px;

    padding: 13px;

    border: none;

    border-radius: 8px;

    background: #238636;

    color: white;

    font-size: 15px;

    font-weight: 600;

    cursor: pointer;

    transition: .15s;
}

button:hover {

    background: #2ea043;
}


/* --------------------------------------------------
   Example
-------------------------------------------------- */

.example {

    margin-top: 14px;

    color: #8b949e;

    font-size: 13px;

    line-height: 1.5;
}

.example code {

    color: #79c0ff;
}


/* --------------------------------------------------
   Diagnosis
-------------------------------------------------- */

.result {

    margin-top: 30px;

    background: #161b22;

    border: 1px solid #30363d;

    border-radius: 12px;

    overflow: hidden;
}

.result-header {

    padding: 15px 20px;

    border-bottom: 1px solid #30363d;

    font-weight: 600;

    display: flex;

    align-items: center;

    gap: 8px;
}

.status {

    width: 9px;

    height: 9px;

    background: #3fb950;

    border-radius: 50%;
}

pre {

    margin: 0;

    padding: 22px;

    background: #0d1117;

    white-space: pre-wrap;

    overflow-wrap: anywhere;

    font-family:
        "SFMono-Regular",
        Consolas,
        "Liberation Mono",
        monospace;

    font-size: 14px;

    line-height: 1.65;

    color: #c9d1d9;
}


/* --------------------------------------------------
   Features
-------------------------------------------------- */

.features {

    display: grid;

    grid-template-columns: repeat(3, 1fr);

    gap: 14px;

    margin-top: 28px;
}

.feature {

    border: 1px solid #21262d;

    border-radius: 8px;

    padding: 15px;

    text-align: center;

    color: #8b949e;

    font-size: 13px;
}

.feature strong {

    display: block;

    color: #e6edf3;

    margin-bottom: 5px;
}


/* --------------------------------------------------
   Footer
-------------------------------------------------- */

footer {

    text-align: center;

    color: #484f58;

    font-size: 12px;

    margin-top: 40px;
}


/* --------------------------------------------------
   Mobile
-------------------------------------------------- */

@media (max-width: 650px) {

    .features {

        grid-template-columns: 1fr;
    }

    .hero h1 {

        font-size: 30px;
    }
}

</style>

</head>


<body>


<header>

<div class="header-content">

<div class="logo">

Cloud<span>Fix</span>

</div>

<div class="badge">

READ-ONLY AWS ACCESS

</div>

</div>

</header>


<div class="container">


<div class="hero">

<h1>AWS access troubleshooting, powered by evidence.</h1>

<p>

CloudFix is an AI troubleshooting agent that inspects your
actual AWS S3 and IAM configuration, identifies the likely
root cause of access failures, and recommends a
least-privilege fix.

</p>

</div>


<div class="card">

<form method="post">

<label class="label">

Describe the AWS access problem

</label>

<textarea
name="question"
placeholder="Why can't cloudfix-demo-user download files from cloudfix-demo-bucket?"
required>{{ question or '' }}</textarea>

<button type="submit">

Diagnose AWS Configuration

</button>

</form>


<div class="example">

Example:
<code>
Why can't cloudfix-demo-user access cloudfix-demo-bucket-yabesh?
</code>

</div>

</div>


{% if answer %}

<div class="result">

<div class="result-header">

<div class="status"></div>

CloudFix Diagnosis

</div>

<pre>{{ answer }}</pre>

</div>

{% endif %}


<div class="features">

<div class="feature">

<strong>Real AWS Evidence</strong>

Inspects actual S3 and IAM configuration through boto3.

</div>


<div class="feature">

<strong>Agentic Diagnosis</strong>

Strands decides which tools to invoke based on the problem.

</div>


<div class="feature">

<strong>Human-in-the-loop</strong>

CloudFix recommends fixes but never modifies your AWS account.

</div>

</div>


<footer>

CloudFix · Strands Agents SDK · boto3 · AWS S3 · AWS IAM

</footer>


</div>


</body>

</html>
"""


@app.route("/", methods=["GET", "POST"])
def index():

    answer = None
    question = ""

    if request.method == "POST":

        question = request.form.get(
            "question",
            ""
        ).strip()

        if question:

            try:

                result = agent(question)

                answer = str(result)

            except Exception as exc:

                answer = (
                    "CloudFix could not complete the diagnosis.\\n\\n"
                    f"Error: {exc}"
                )

    return render_template_string(
        PAGE,
        answer=answer,
        question=question,
    )


if __name__ == "__main__":

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True,
    )
