import os
from datetime import datetime

import resend
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse
from sqlalchemy import create_engine, text

app = FastAPI()

# SQLite DB in project folder
engine = create_engine("sqlite:///rcpt.db", connect_args={"check_same_thread": False})


def init_db():
    with engine.begin() as conn:
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS claims (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            merchant_id TEXT NOT NULL,
            email TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """))

        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            merchant_id TEXT NOT NULL,
            email TEXT NOT NULL,
            total_cents INTEGER NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """))


init_db()


def send_receipt_email(to_email: str, merchant_id: str, total_huf: int, sale_id: int):
    api_key = os.getenv("RESEND_API_KEY")
    if not api_key:
        raise RuntimeError("RESEND_API_KEY is not set")

    resend.api_key = api_key

    subject = f"Your RCPT receipt from {merchant_id}"

    # Local link won't open on phone yet (until deployment), but email delivery works now.
    receipt_url = f"https://rcpt-mvp.onrender.com/r/{sale_id}"

    html = f"""
    <div style="font-family: Arial, sans-serif; line-height: 1.4;">
      <h2>RCPT Receipt</h2>
      <p><b>Merchant:</b> {merchant_id}</p>
      <p><b>Total:</b> {total_huf} HUF</p>
      <p><b>Receipt ID:</b> {sale_id}</p>
      <p><b>View (local for now):</b> <a href="{receipt_url}">{receipt_url}</a></p>
      <hr />
      <p>This is a prototype email.</p>
    </div>
    """

    resend.Emails.send({
        "from": "RCPT Receipts <receipts@rcpt.digital>",
        "to": [to_email],
        "subject": subject,
        "html": html,
    })


@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <html><body>
      <h1>Hello RCPT</h1>
      <ul>
        <li><a href="/m/test">Tap page: /m/test</a></li>
        <li><a href="/pos/test">POS page: /pos/test</a></li>
      </ul>
    </body></html>
    """


@app.get("/m/{merchant_id}", response_class=HTMLResponse)
def tap_page(merchant_id: str):
    return f"""
    <html><body>
      <h1>RCPT</h1>
      <p>Merchant: <b>{merchant_id}</b></p>
      <p>Enter your email to receive your receipt.</p>

      <form method="post" action="/m/{merchant_id}/claim">
        <input type="email" name="email" placeholder="you@email.com" required />
        <button type="submit">Send receipt</button>
      </form>

      <p style="margin-top:16px;">
        Debug: <a href="/debug/claims">/debug/claims</a>
      </p>
    </body></html>
    """


@app.post("/m/{merchant_id}/claim", response_class=HTMLResponse)
def claim_email(merchant_id: str, email: str = Form(...)):
    created_at = datetime.utcnow().isoformat()

    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO claims (merchant_id, email, created_at) VALUES (:m, :e, :t)"),
            {"m": merchant_id, "e": email, "t": created_at},
        )

    return f"""
    <html><body>
      <h1>✅ Email saved</h1>
      <p>Merchant: <b>{merchant_id}</b></p>
      <p>Email: <b>{email}</b></p>
      <p><a href="/pos/{merchant_id}">Go to POS</a></p>
    </body></html>
    """


@app.get("/pos/{merchant_id}", response_class=HTMLResponse)
def pos_screen(merchant_id: str):
    return f"""
    <html><body>
      <h1>Simulated POS</h1>
      <p>Merchant: <b>{merchant_id}</b></p>

      <form method="post" action="/pos/{merchant_id}/paid">
        <label>Total (HUF): </label>
        <input type="number" name="total_huf" value="1990" min="0" required />
        <button type="submit">Mark Paid</button>
      </form>

      <p style="margin-top:16px;">
        Debug: <a href="/debug/claims">claims</a>
      </p>
    </body></html>
    """


@app.post("/pos/{merchant_id}/paid", response_class=HTMLResponse)
def pos_paid(merchant_id: str, total_huf: int = Form(...)):
    with engine.begin() as conn:
        claim = conn.execute(
            text("""
                SELECT id, email
                FROM claims
                WHERE merchant_id = :m
                ORDER BY id DESC
                LIMIT 1
            """),
            {"m": merchant_id},
        ).fetchone()

        if not claim:
            return f"""
            <html><body>
              <h1>⚠️ No customer email yet</h1>
              <p>Go to <a href="/m/{merchant_id}">/m/{merchant_id}</a> and submit an email first.</p>
              <p><a href="/pos/{merchant_id}">Back to POS</a></p>
            </body></html>
            """

        sale = conn.execute(
            text("""
                INSERT INTO sales (merchant_id, email, total_cents, status, created_at)
                VALUES (:m, :e, :t, 'PAID', :c)
            """),
            {
                "m": merchant_id,
                "e": claim.email,
                "t": total_huf * 100,
                "c": datetime.utcnow().isoformat(),
            },
        )
        sale_id = sale.lastrowid

    # Send email after DB commit (keeps DB consistent even if email fails)
    try:
        send_receipt_email(
            to_email=claim.email,
            merchant_id=merchant_id,
            total_huf=total_huf,
            sale_id=sale_id,
        )
        email_status = "✅ Email sent"
    except Exception as e:
        email_status = f"⚠️ Email failed: {e}"

    return f"""
    <html><body>
      <h1>✅ Paid recorded</h1>
      <p>Sale ID: <b>{sale_id}</b></p>
      <p>{email_status}</p>
      <p><a href="/r/{sale_id}">View receipt</a></p>
      <p><a href="/pos/{merchant_id}">Back to POS</a></p>
    </body></html>
    """


@app.get("/r/{sale_id}", response_class=HTMLResponse)
def receipt_page(sale_id: int):
    with engine.begin() as conn:
        sale = conn.execute(
            text("""
                SELECT id, merchant_id, email, total_cents, status, created_at
                FROM sales
                WHERE id = :id
            """),
            {"id": sale_id},
        ).fetchone()

    if not sale:
        return "<h1>Receipt not found</h1>"

    total_huf = sale.total_cents // 100

    return f"""
    <html><body>
      <h1>RCPT Receipt</h1>
      <p><b>Receipt ID:</b> {sale.id}</p>
      <p><b>Merchant:</b> {sale.merchant_id}</p>
      <p><b>Customer Email:</b> {sale.email}</p>
      <p><b>Status:</b> {sale.status}</p>
      <p><b>Total:</b> {total_huf} HUF</p>
      <p><b>Date (UTC):</b> {sale.created_at}</p>
    </body></html>
    """


@app.get("/debug/claims", response_class=HTMLResponse)
def debug_claims():
    with engine.begin() as conn:
        rows = conn.execute(
            text("SELECT id, merchant_id, email, created_at FROM claims ORDER BY id DESC")
        ).fetchall()

    items = "".join(
        f"<li>#{r.id} | {r.merchant_id} | {r.email} | {r.created_at}</li>"
        for r in rows
    )

    return f"""
    <html><body>
      <h1>Saved Claims</h1>
      <ul>{items}</ul>
      <p><a href="/m/test">Back to /m/test</a></p>
    </body></html>
    """
