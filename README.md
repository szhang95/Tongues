<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>DevilTongues — Synthetic Bond Arbitrage</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="Real-Time Synthetic Bond Arbitrage Detection Platform">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
  <style>
    :root{
      --bg:#0b1222;
      --panel:#0f1b34;
      --ink:#eaf1ff;
      --muted:#a7b3d1;
      --brand:#3b82f6;
      --brand-2:#2563eb;
      --card:#0f172a;
      --ring:#4463ff;
      --ok:#10b981;
      --warn:#f59e0b;
    }
    *{box-sizing:border-box}
    html,body{height:100%}
    body{
      margin:0;
      font-family:Inter,system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;
      color:var(--ink);
      background:
        radial-gradient(1200px 600px at 50% -200px, #132246 0%, rgba(19,34,70,0) 60%),
        radial-gradient(900px 400px at 100% 0, #0c1a38 0%, rgba(12,26,56,0) 70%),
        linear-gradient(180deg, #0b1222 0%, #0b1222 100%);
    }
    .wrap{max-width:1200px;margin:0 auto;padding:48px 20px 80px}
    .hero{
      background:linear-gradient(145deg, rgba(37,99,235,.22), rgba(59,130,246,.08));
      border:1px solid rgba(68,99,255,.25);
      box-shadow:0 20px 60px rgba(0,0,0,.35), inset 0 0 80px rgba(68,99,255,.12);
      border-radius:28px;
      padding:60px 24px;
      text-align:center;
    }
    h1{font-size:64px;line-height:1.05;margin:0 0 12px}
    .sub{font-size:28px;color:var(--muted);margin:0 0 28px}
    .chips{display:flex;gap:12px;justify-content:center;flex-wrap:wrap;margin-bottom:28px}
    .chip{
      background:rgba(255,255,255,.08);
      border:1px solid rgba(255,255,255,.16);
      padding:10px 16px;border-radius:999px;font-weight:600
    }
    .cta{
      display:inline-block;background:linear-gradient(135deg,var(--brand),var(--brand-2));
      color:#fff;text-decoration:none;font-weight:700;
      padding:16px 28px;border-radius:14px;border:1px solid rgba(255,255,255,.2);
      box-shadow:0 8px 20px rgba(59,130,246,.35);
    }
    .section{margin-top:56px}
    h2{font-size:36px;margin:0 0 16px}
    p.lead{color:var(--muted);margin:0 0 24px}
    /* two-by-two grid */
    .grid{
      display:grid;gap:18px;
      grid-template-columns:repeat(2,minmax(260px,1fr));
    }
    @media (max-width:820px){
      .grid{grid-template-columns:1fr}
      h1{font-size:44px}
    }
    .card{
      background:var(--panel);
      border:1px solid rgba(255,255,255,.09);
      border-top:3px solid var(--ring);
      border-radius:16px;padding:22px;
      box-shadow:0 10px 30px rgba(0,0,0,.25);
      min-height:150px
    }
    .card h3{margin:0 0 6px}
    .card p{margin:0;color:var(--muted)}
    .code{
      background:#0e1a2f;color:#d8e3ff;border:1px solid rgba(255,255,255,.08);
      border-radius:14px;padding:18px;overflow:auto;font-family:ui-monospace,Menlo,Consolas,monospace
    }
    .footer{opacity:.7;text-align:center;margin-top:56px;font-size:14px}
    a.inline{color:#93b4ff;text-decoration:none;border-bottom:1px dashed rgba(147,180,255,.5)}
  </style>
</head>
<body>
  <div class="wrap">
    <header class="hero">
      <h1>DevilTongues</h1>
      <p class="sub">Real-Time Synthetic Bond Arbitrage Detection Platform</p>
      <div class="chips">
        <span class="chip">Python</span>
        <span class="chip">LSEG Refinitiv</span>
        <span class="chip">Options Trading</span>
        <span class="chip">Quantitative Finance</span>
      </div>
      <a class="cta" href="https://github.com/deviltongues/Tongues">Get Started on GitHub</a>
    </header>

    <section class="section">
      <h2>Features</h2>
      <p class="lead">Each capability is described separately to keep things clear and focused.</p>
      <div class="grid">
        <div class="card">
          <h3>Real-Time Market Data</h3>
          <p>Live spot prices and options chains from LSEG Refinitiv with bid/ask/last and exchange timestamps.</p>
        </div>
        <div class="card">
          <h3>Arbitrage Detection</h3>
          <p>Put-call parity monitoring, implied rate estimation, and threshold-based opportunity signals.</p>
        </div>
        <div class="card">
          <h3>Strategy Analysis</h3>
          <p>Exact legs, risks, recommendations, and P&amp;L components including scenario analysis.</p>
        </div>
        <div class="card">
          <h3>3D Visualization</h3>
          <p>Interactive surface of implied r vs. strike and time to expiry with “% annualized” labeling.</p>
        </div>
      </div>
    </section>

    <section class="section">
      <h2>Quick Start</h2>
      <div class="code"><pre># 1) Clone
git clone https://github.com/deviltongues/Tongues.git
cd Tongues</pre></div>

      <div class="code" style="margin-top:14px;"><pre># 2) Create virtual environment
python -m venv .venv</pre></div>

      <div class="code" style="margin-top:14px;"><pre># 3) Activate on Windows
.venv\Scripts\activate</pre></div>

      <div class="code" style="margin-top:14px;"><pre># 3) Activate on macOS/Linux
source .venv/bin/activate</pre></div>

      <div class="code" style="margin-top:14px;"><pre># 4) Install
pip install -e .</pre></div>

      <div class="code" style="margin-top:14px;"><pre># 5) Run
shiny run app.py
# App starts at http://127.0.0.1:8000</pre></div>
    </section>

    <section class="section">
      <h2>Project Structure</h2>
      <div class="code"><pre>Tongues/
├─ app.py
├─ modern.css
├─ custom.css
├─ pyproject.toml
├─ requirements.txt
├─ README.md
├─ index.html
├─ CNAME
├─ src/
│  └─ deviltongues/
│     ├─ __init__.py
│     ├─ fetch_options.py
│     └─ utilities.py
└─ old code/</pre></div>
    </section>

    <p class="footer">
      Created by Sunny Zhang &amp; Victoria Li •
      <a class="inline" href="https://github.com/deviltongues/Tongues">GitHub</a> •
      <a class="inline" href="https://www.deviltongues.website">Website</a>
    </p>
  </div>
</body>
</html>
