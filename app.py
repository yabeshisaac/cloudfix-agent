"""
Minimal Flask UI for CloudFix.

Run:
    python app.py
Then open http://localhost:5000

Build/wire this up LAST -- get agent.py working from the CLI first.
"""

from flask import Flask, render_template_string, request

from agent import build_agent

app = Flask(__name__)
agent = build_agent()  # built once at startup; Strands agent keeps history per-process

PAGE = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>CloudFix</title>
  <style>
    body { font-family: -apple-system, Segoe UI, sans-serif; max-width: 760px;
           margin: 40px auto; padding: 0 16px; background: #0b0f14; color: #e6edf3; }
    h1 { font-size: 1.4rem; }
    textarea { width: 100%; box-sizing: border-box; padding: 10px; font-size: 1rem;
               border-radius: 6px; border: 1px solid #30363d; background: #161b22; color: #e6edf3; }
    button { margin-top: 10px; padding: 8px 18px; font-size: 1rem; border-radius: 6px;
             border: none; background: #2f81f7; color: white; cursor: pointer; }
    pre { white-space: pre-wrap; background: #161b22; padding: 16px; border-radius: 6px;
          border: 1px solid #30363d; }
    .hint { color: #8b949e; font-size: 0.9rem; }
  </style>
</head>
<body>
  <h1>🛠️ CloudFix</h1>
  <p class="hint">Describe an S3/IAM access problem. e.g. "Why can't cloudfix-demo-user download files from cloudfix-demo-bucket?"</p>
  <form method="post">
    <textarea name="question" rows="3" placeholder="Why can't ... access ...?">{{ question or '' }}</textarea><br>
    <button type="submit">Diagnose</button>
  </form>
  {% if answer %}
    <h3>Diagnosis</h3>
    <pre>{{ answer }}</pre>
  {% endif %}
</body>
</html>
"""


@app.route("/", methods=["GET", "POST"])
def index():
    answer = None
    question = None
    if request.method == "POST":
        question = request.form.get("question", "").strip()
        if question:
            result = agent(question)
            answer = str(result)
    return render_template_string(PAGE, answer=answer, question=question)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
