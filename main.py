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
        conn.execute(
            text(
                """
        CREATE TABLE IF NOT EXISTS claims (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            merchant_id TEXT NOT NULL,
            email TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
            )
        )

        conn.execute(
            text(
                """
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            merchant_id TEXT NOT NULL,
            email TEXT NOT NULL,
            total_cents INTEGER NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
            )
        )


def _has_column(conn, table: str, col: str) -> bool:
    cols = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
    return any(c[1] == col for c in cols)


def migrate_db():
    # Adds Phase 2 columns without breaking existing DBs
    with engine.begin() as conn:
        if not _has_column(conn, "claims", "device_id"):
            conn.execute(text("ALTER TABLE claims ADD COLUMN device_id TEXT"))
        if not _has_column(conn, "sales", "device_id"):
            conn.execute(text("ALTER TABLE sales ADD COLUMN device_id TEXT"))


init_db()
migrate_db()


def send_receipt_email(to_email: str, merchant_id: str, total_pkr: int, sale_id: int):
    api_key = os.getenv("RESEND_API_KEY")
    if not api_key:
        raise RuntimeError("RESEND_API_KEY is not set")

    resend.api_key = api_key

    subject = f"Your RCPT receipt from {merchant_id}"
    receipt_url = f"https://rcpt-mvp.onrender.com/r/{sale_id}"

    html = f"""
    <div style="font-family: Arial, sans-serif; line-height: 1.4;">
      <h2>RCPT Receipt</h2>
      <p><b>Merchant:</b> {merchant_id}</p>
      <p><b>Total:</b> {total_pkr} PKR</p>
      <p><b>Receipt ID:</b> {sale_id}</p>
      <p><b>View:</b> <a href="{receipt_url}">{receipt_url}</a></p>
      <hr />
      <p>This is a prototype email.</p>
    </div>
    """

    resend.Emails.send(
        {
            "from": "RCPT Receipts <receipts@rcpt.digital>",
            "to": [to_email],
            "subject": subject,
            "html": html,
        }
    )


@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <html><body>
      <h1>Hello RCPT</h1>
      <ul>
        <li><a href="/m/test">Tap page: /m/test</a></li>
        <li><a href="/pos/test">POS page: /pos/test</a></li>
        <li><a href="/v">Vault: /v</a></li>
      </ul>
    </body></html>
    """


# -----------------------------
# Tap + Claim (Consumer side)
# -----------------------------
@app.get("/m/{merchant_id}", response_class=HTMLResponse)
def tap_page(merchant_id: str):
    # NOTE: This is an f-string, so JS braces must be doubled {{ }}
    return f"""
    <html><body>
      <h1>RCPT</h1>
      <p>Merchant: <b>{merchant_id}</b></p>

      <p>
        Your Vault works with <b>no account</b>. Optional: add email if you also want a copy.
      </p>

      <form method="post" action="/m/{merchant_id}/claim">
        <input type="hidden" name="device_id" id="device_id" />
        <input type="email" name="email" placeholder="optional@email.com" />
        <button type="submit">Continue</button>
      </form>

      <p style="margin-top:16px;">
        <a href="/v">Open my Vault</a> |
        Debug: <a href="/debug/claims">/debug/claims</a>
      </p>

      <script>
      (function() {{
        let id = localStorage.getItem("rcpt_device_id");
        if (!id) {{
          id = crypto.randomUUID();
          localStorage.setItem("rcpt_device_id", id);
        }}
        document.getElementById("device_id").value = id;
      }})();
      </script>
    </body></html>
    """


@app.post("/m/{merchant_id}/claim", response_class=HTMLResponse)
def claim_email(
    merchant_id: str,
    device_id: str = Form(...),
    email: str = Form(""),
):
    created_at = datetime.utcnow().isoformat()

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO claims (merchant_id, email, device_id, created_at)
                VALUES (:m, :e, :d, :t)
                """
            ),
            {"m": merchant_id, "e": email, "d": device_id, "t": created_at},
        )

    return f"""
    <html><body>
      <h1>✅ Linked</h1>
      <p>Merchant: <b>{merchant_id}</b></p>
      <p>Device ID: <code>{device_id}</code></p>
      <p>Email copy: <b>{email if email else "(none)"}</b></p>
      <p><a href="/v">Open my Vault</a></p>
      <p><a href="/pos/{merchant_id}">Go to POS</a></p>
    </body></html>
    """


# -----------------------------
# POS (Merchant side)
# -----------------------------
@app.get("/pos/{merchant_id}", response_class=HTMLResponse)
def pos_screen(merchant_id: str):
    return f"""
    <html><body>
      <h1>Simulated POS</h1>
      <p>Merchant: <b>{merchant_id}</b></p>

      <form method="post" action="/pos/{merchant_id}/paid">
        <label>Total (PKR): </label>
        <input type="number" name="total_pkr" value="1990" min="0" required />
        <button type="submit">Mark Paid</button>
      </form>

      <p style="margin-top:16px;">
        Debug: <a href="/debug/claims">claims</a>
      </p>
    </body></html>
    """


@app.post("/pos/{merchant_id}/paid", response_class=HTMLResponse)
def pos_paid(merchant_id: str, total_pkr: int = Form(...)):
    with engine.begin() as conn:
        claim = conn.execute(
            text(
                """
                SELECT id, email, device_id
                FROM claims
                WHERE merchant_id = :m
                ORDER BY id DESC
                LIMIT 1
                """
            ),
            {"m": merchant_id},
        ).fetchone()

        if not claim:
            return f"""
            <html><body>
              <h1>⚠️ No customer claim yet</h1>
              <p>Go to <a href="/m/{merchant_id}">/m/{merchant_id}</a> and continue (Vault + optional email).</p>
              <p><a href="/pos/{merchant_id}">Back to POS</a></p>
            </body></html>
            """

        sale = conn.execute(
            text(
                """
                INSERT INTO sales (merchant_id, email, device_id, total_cents, status, created_at)
                VALUES (:m, :e, :d, :t, 'PAID', :c)
                """
            ),
            {
                "m": merchant_id,
                "e": claim.email or "",
                "d": claim.device_id or "",
                "t": total_pkr * 100,
                "c": datetime.utcnow().isoformat(),
            },
        )
        sale_id = sale.lastrowid

    # Optional email (Vault is default)
    if claim.email:
        try:
            send_receipt_email(
                to_email=claim.email,
                merchant_id=merchant_id,
                total_pkr=total_pkr,
                sale_id=sale_id,
            )
            email_status = "✅ Email sent"
        except Exception as e:
            email_status = f"⚠️ Email failed: {e}"
    else:
        email_status = "ℹ️ No email provided (Vault only)"

    return f"""
    <html><body>
      <h1>✅ Paid recorded</h1>
      <p>Sale ID: <b>{sale_id}</b></p>
      <p>{email_status}</p>
      <p><a href="/r/{sale_id}">View receipt</a></p>
      <p><a href="/v">Open Vault</a></p>
      <p><a href="/pos/{merchant_id}">Back to POS</a></p>
    </body></html>
    """


# -----------------------------
# Receipt page
# -----------------------------
@app.get("/r/{sale_id}", response_class=HTMLResponse)
def receipt_page(sale_id: int):
    with engine.begin() as conn:
        sale = conn.execute(
            text(
                """
                SELECT id, merchant_id, email, device_id, total_cents, status, created_at
                FROM sales
                WHERE id = :id
                """
            ),
            {"id": sale_id},
        ).fetchone()

    if not sale:
        return "<h1>Receipt not found</h1>"

    total_pkr = sale.total_cents // 100

    return f"""
    <html><body>
      <h1>RCPT Receipt</h1>
      <p><b>Receipt ID:</b> {sale.id}</p>
      <p><b>Merchant:</b> {sale.merchant_id}</p>
      <p><b>Status:</b> {sale.status}</p>
      <p><b>Total:</b> {total_pkr} PKR</p>
      <p><b>Date (UTC):</b> {sale.created_at}</p>
      <hr/>
      <p><b>Vault Device ID:</b> <code>{sale.device_id or ""}</code></p>
      <p><b>Email copy:</b> {sale.email if sale.email else "(none)"}</p>
      <p><a href="/v">Back to Vault</a></p>
    </body></html>
    """


# -----------------------------
# Vault (Consumer side)
# -----------------------------
@app.get("/v", response_class=HTMLResponse)
def vault_page():
    # Not an f-string, so normal JS braces are OK here.
    return """
    <html><body>
      <h1>My RCPT Vault</h1>
      <p>This Vault is tied to your device (no account).</p>

      <div id="out">Loading…</div>

      <p style="margin-top:16px;">
        <a href="/m/test">Tap demo (/m/test)</a>
      </p>

      <script>
        (async function () {
          let id = localStorage.getItem("rcpt_device_id");
          if (!id) {
            id = crypto.randomUUID();
            localStorage.setItem("rcpt_device_id", id);
          }

          const res = await fetch(`/api/vault/${id}`);
          const data = await res.json();

          if (!data.receipts || data.receipts.length === 0) {
            document.getElementById("out").innerHTML = `
              <p><b>No receipts yet.</b></p>
              <p>Go to a tap page first (e.g. /m/test), then mark paid in POS.</p>
              <p><code>Device ID:</code> ${id}</p>
            `;
            return;
          }

          const items = data.receipts.map(r => `
            <li>
              <a href="/r/${r.id}">Receipt #${r.id}</a>
              — <b>${r.merchant_id}</b>
              — ${r.total_pkr} PKR
              — <small>${r.created_at}</small>
            </li>
          `).join("");

          document.getElementById("out").innerHTML = `
            <p><code>Device ID:</code> ${data.device_id}</p>
            <ul>${items}</ul>
          `;
        })();
      </script>
    </body></html>
    """


@app.get("/api/vault/{device_id}")
def vault_api(device_id: str):
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT id, merchant_id, total_cents, created_at
                FROM sales
                WHERE device_id = :d
                ORDER BY id DESC
                """
            ),
            {"d": device_id},
        ).fetchall()

    receipts = [
        {
            "id": r.id,
            "merchant_id": r.merchant_id,
            "total_pkr": r.total_cents // 100,
            "created_at": r.created_at,
        }
        for r in rows
    ]
    return {"device_id": device_id, "receipts": receipts}


# -----------------------------
# Debug
# -----------------------------
@app.get("/debug/claims", response_class=HTMLResponse)
def debug_claims():
    with engine.begin() as conn:
        rows = conn.execute(
            text("SELECT id, merchant_id, email, device_id, created_at FROM claims ORDER BY id DESC")
        ).fetchall()

    items = "".join(
        f"<li>#{r.id} | {r.merchant_id} | {r.email} | {r.device_id} | {r.created_at}</li>"
        for r in rows
    )

    return f"""
    <html><body>
      <h1>Saved Claims</h1>
      <ul>{items}</ul>
      <p><a href="/m/test">Back to /m/test</a></p>
    </body></html>
    """