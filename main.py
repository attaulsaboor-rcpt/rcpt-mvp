import os
import json
from datetime import datetime
from typing import List, Optional

import resend
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy import create_engine, text

app = FastAPI()

# SQLite DB in project folder
engine = create_engine("sqlite:///rcpt.db", connect_args={"check_same_thread": False})


BASE_STYLE = """
<style>
  :root {
    --bg: #f5f5f7;
    --card: #ffffff;
    --text: #1d1d1f;
    --muted: #6e6e73;
    --line: #e5e5ea;
    --btn: #111111;
    --btn-text: #ffffff;
    --secondary: #f2f2f4;
    --radius: 16px;
    --radius-sm: 12px;
    --shadow: 0 10px 30px rgba(0, 0, 0, 0.06);
  }

  * { box-sizing: border-box; }
  body {
    margin: 0;
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.45;
  }
  .container {
    max-width: 760px;
    margin: 0 auto;
    padding: 24px 16px 48px;
  }
  .logo {
    font-weight: 700;
    font-size: 13px;
    letter-spacing: 0.14em;
    color: var(--muted);
    margin-bottom: 14px;
  }
  .card {
    background: var(--card);
    border-radius: var(--radius);
    box-shadow: var(--shadow);
    padding: 24px;
  }
  h1, h2, h3 {
    margin: 0 0 10px;
    line-height: 1.2;
    letter-spacing: -0.01em;
  }
  p { margin: 0 0 12px; }
  .row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 14px 0;
    border-bottom: 1px solid var(--line);
  }
  .row:last-child {
    border-bottom: none;
    padding-bottom: 0;
  }
  .meta {
    background: #fafafa;
    border: 1px solid var(--line);
    border-radius: var(--radius-sm);
    padding: 14px;
    margin-top: 14px;
  }
  .meta p:last-child { margin-bottom: 0; }
  .muted {
    color: var(--muted);
    font-size: 13px;
  }
  .pill {
    display: inline-flex;
    align-items: center;
    border-radius: 999px;
    padding: 6px 10px;
    font-size: 12px;
    font-weight: 600;
    border: 1px solid transparent;
  }
  .pill.paid {
    color: #0f6b2e;
    background: #ebf9ef;
    border-color: #cdeed7;
  }
  .pill.claimed {
    color: #0b5394;
    background: #eaf4ff;
    border-color: #cddff4;
  }
  .pill.draft {
    color: #6e6e73;
    background: #f2f2f4;
    border-color: #e5e5ea;
  }
  form { margin-top: 14px; }
  input[type="email"], input[type="number"], input[type="text"] {
    width: 100%;
    margin: 8px 0 12px;
    padding: 11px 12px;
    border: 1px solid #d2d2d7;
    border-radius: 12px;
    background: #fff;
    color: var(--text);
    font-size: 15px;
    outline: none;
  }
  input[type="email"]:focus, input[type="number"]:focus, input[type="text"]:focus {
    border-color: #7f7f85;
    box-shadow: 0 0 0 4px rgba(17, 17, 17, 0.08);
  }
  .btn, .btn-secondary {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border: 0;
    border-radius: 12px;
    padding: 11px 15px;
    font-size: 14px;
    text-decoration: none;
    cursor: pointer;
  }
  .btn {
    background: var(--btn);
    color: var(--btn-text);
  }
  .btn-secondary {
    background: var(--secondary);
    color: var(--text);
  }
  a {
    color: inherit;
  }
  .actions {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    margin-top: 14px;
  }
  .amount {
    font-size: clamp(36px, 7vw, 52px);
    line-height: 1;
    font-weight: 700;
    letter-spacing: -0.02em;
    margin: 10px 0 12px;
  }
  code {
    font-size: 12px;
    background: #f2f2f4;
    padding: 2px 6px;
    border-radius: 8px;
  }
  ul.clean {
    list-style: none;
    margin: 12px 0 0;
    padding: 0;
  }
  li.row {
    display: block;
    padding: 14px 0;
    border-bottom: 1px solid var(--line);
  }
  li.row:last-child {
    border-bottom: none;
    padding-bottom: 0;
  }
  li.row a {
    font-weight: 600;
    text-decoration: none;
  }
  li.row a:hover {
    text-decoration: underline;
  }
  li.row small {
    color: var(--muted);
  }
  @media (max-width: 560px) {
    .card {
      padding: 18px;
      border-radius: 14px;
    }
  }
</style>
"""

# -----------------------------
# Pydantic Models for Bridge Ingestion
# -----------------------------
class ReceiptItemIn(BaseModel):
    name: str
    qty: Optional[int] = None
    unitPrice: Optional[float] = None
    linePrice: Optional[float] = None

class ReceiptIn(BaseModel):
    merchant: Optional[str] = None
    date: Optional[str] = None
    cashier: Optional[str] = None
    paymentMethod: Optional[str] = None
    subtotal: Optional[float] = None
    discount: Optional[float] = None
    tax: Optional[float] = None
    total: Optional[float] = None
    items: List[ReceiptItemIn] = []

class ReceiptIngestPayload(BaseModel):
    terminal_id: str
    source_file: str
    captured_at_utc: str
    receipt: ReceiptIn


def status_pill(status: str) -> str:
    normalized = (status or "DRAFT").upper()
    cls = "draft"
    if normalized == "PAID":
        cls = "paid"
    elif normalized == "CLAIMED":
        cls = "claimed"
    return f'<span class="pill {cls}">{normalized}</span>'


def render_page(title: str, body_html: str) -> str:
    return f"""
    <html>
      <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>{title}</title>
        {BASE_STYLE}
      </head>
      <body>
        <main class="container">
          <div class="logo">RCPT</div>
          {body_html}
        </main>
      </body>
    </html>
    """


def _utcnow() -> str:
    return datetime.utcnow().isoformat()


def _public_base_url() -> str:
    # Use env var if you want (recommended on Render),
    # otherwise default to your custom domain.
    return (os.getenv("PUBLIC_BASE_URL") or "https://rcpt.digital").rstrip("/")


def init_db():
    with engine.begin() as conn:
        # Phase 2 legacy tables
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

        # Phase 3 receipts table (Option C)
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS receipts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    terminal_id TEXT,
                    merchant_id TEXT,
                    total_cents INTEGER NOT NULL,
                    currency TEXT DEFAULT 'PKR',
                    status TEXT DEFAULT 'DRAFT',
                    created_at TEXT NOT NULL,
                    updated_at TEXT,
                    paid_at TEXT,
                    claimed_at TEXT,
                    claimed_by_device_id TEXT,
                    email TEXT,
                    items_json TEXT
                )
                """
            )
        )


def _has_column(conn, table: str, col: str) -> bool:
    cols = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
    return any(c[1] == col for c in cols)


def migrate_db():
    """
    Additive, non-breaking migration:
    - Keeps Phase 2 DBs working
    - Adds/extends receipts schema (Phase 3 Option C)
    - Backfills sane defaults for existing rows
    """
    with engine.begin() as conn:
        # Phase 2 device_id columns
        if not _has_column(conn, "claims", "device_id"):
            conn.execute(text("ALTER TABLE claims ADD COLUMN device_id TEXT"))
        if not _has_column(conn, "sales", "device_id"):
            conn.execute(text("ALTER TABLE sales ADD COLUMN device_id TEXT"))

        # Ensure receipts exists (for older DBs that didn't have it)
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS receipts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    terminal_id TEXT,
                    merchant_id TEXT,
                    total_cents INTEGER NOT NULL,
                    currency TEXT DEFAULT 'PKR',
                    status TEXT DEFAULT 'DRAFT',
                    created_at TEXT NOT NULL,
                    updated_at TEXT,
                    paid_at TEXT,
                    claimed_at TEXT,
                    claimed_by_device_id TEXT,
                    email TEXT,
                    items_json TEXT
                )
                """
            )
        )

        # Add missing columns if receipts was created earlier with fewer cols
        if not _has_column(conn, "receipts", "terminal_id"):
            conn.execute(text("ALTER TABLE receipts ADD COLUMN terminal_id TEXT"))
        if not _has_column(conn, "receipts", "merchant_id"):
            conn.execute(text("ALTER TABLE receipts ADD COLUMN merchant_id TEXT"))
        if not _has_column(conn, "receipts", "currency"):
            conn.execute(text("ALTER TABLE receipts ADD COLUMN currency TEXT"))
        if not _has_column(conn, "receipts", "status"):
            conn.execute(text("ALTER TABLE receipts ADD COLUMN status TEXT"))
        if not _has_column(conn, "receipts", "updated_at"):
            conn.execute(text("ALTER TABLE receipts ADD COLUMN updated_at TEXT"))
        if not _has_column(conn, "receipts", "paid_at"):
            conn.execute(text("ALTER TABLE receipts ADD COLUMN paid_at TEXT"))
        if not _has_column(conn, "receipts", "claimed_at"):
            conn.execute(text("ALTER TABLE receipts ADD COLUMN claimed_at TEXT"))
        if not _has_column(conn, "receipts", "claimed_by_device_id"):
            conn.execute(text("ALTER TABLE receipts ADD COLUMN claimed_by_device_id TEXT"))
        if not _has_column(conn, "receipts", "email"):
            conn.execute(text("ALTER TABLE receipts ADD COLUMN email TEXT"))
        if not _has_column(conn, "receipts", "items_json"):
            conn.execute(text("ALTER TABLE receipts ADD COLUMN items_json TEXT"))

        # Backfill defaults for older rows
        conn.execute(text("UPDATE receipts SET status='DRAFT' WHERE status IS NULL"))
        conn.execute(text("UPDATE receipts SET currency='PKR' WHERE currency IS NULL"))
        conn.execute(text("UPDATE receipts SET updated_at=created_at WHERE updated_at IS NULL"))
        conn.execute(text("UPDATE receipts SET terminal_id='legacy' WHERE terminal_id IS NULL"))


init_db()
migrate_db()


def send_receipt_email(to_email: str, merchant_id: str, total_pkr: int, receipt_id: int):
    api_key = os.getenv("RESEND_API_KEY")
    if not api_key:
        raise RuntimeError("RESEND_API_KEY is not set")

    resend.api_key = api_key

    subject = f"Your RCPT receipt from {merchant_id}"
    receipt_url = f"{_public_base_url()}/r/{receipt_id}"

    html = f"""
    <div style="font-family: Arial, sans-serif; line-height: 1.4;">
      <h2>RCPT Receipt</h2>
      <p><b>Merchant:</b> {merchant_id}</p>
      <p><b>Total:</b> {total_pkr} PKR</p>
      <p><b>Receipt ID:</b> {receipt_id}</p>
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
    body = """
    <section class="card">
      <h1>RCPT Prototype</h1>
      <p class="muted">Simple receipt capture and vault access flow.</p>
      <div class="actions">
        <a class="btn" href="/pos/test">Open POS Demo</a>
        <a class="btn-secondary" href="/t/test">Open Terminal Demo</a>
        <a class="btn-secondary" href="/v">Open Vault</a>
      </div>
    </section>
    """
    return render_page("RCPT", body)


# -----------------------------
# Bridge Ingestion API
# -----------------------------
@app.post("/api/receipts/ingest")
def ingest_receipt(payload: ReceiptIngestPayload):
    now = _utcnow()
    
    # Safely handle null total and convert exactly to cents
    total_val = payload.receipt.total or 0.0
    total_cents = int(round(total_val * 100))
    
    # Fallback to terminal_id if heuristic extraction missed the merchant name
    merchant_id = payload.receipt.merchant or payload.terminal_id
    
    # Dump the full structured object to items_json, plus metadata for dedupe
    receipt_dict = payload.receipt.dict()
    receipt_dict["_meta"] = {
        "source_file": payload.source_file,
        "captured_at_utc": payload.captured_at_utc
    }
    items_json_str = json.dumps(receipt_dict)

    with engine.begin() as conn:
        # Lightweight deduplication guard: prevents the same bridge file from creating double records
        dedupe_query = text("""
            SELECT id FROM receipts 
            WHERE terminal_id = :t 
              AND items_json LIKE :s 
            LIMIT 1
        """)
        existing = conn.execute(dedupe_query, {
            "t": payload.terminal_id, 
            "s": f'%"{payload.source_file}"%'
        }).fetchone()
        
        if existing:
            return {
                "ok": True, 
                "receipt_id": existing.id, 
                "terminal_id": payload.terminal_id,
                "note": "duplicate skipped"
            }

        # Insert as an unclaimed PAID receipt waiting for the customer to tap
        insert_query = text("""
            INSERT INTO receipts (
                terminal_id,
                merchant_id,
                total_cents,
                currency,
                status,
                created_at,
                updated_at,
                paid_at,
                claimed_at,
                claimed_by_device_id,
                email,
                items_json
            )
            VALUES (
                :terminal, :m, :t, 'PKR', 'PAID', :now, :now, :now, NULL, NULL, NULL, :items
            )
        """)
        
        result = conn.execute(insert_query, {
            "terminal": payload.terminal_id,
            "m": merchant_id,
            "t": total_cents,
            "now": now,
            "items": items_json_str
        })
        receipt_id = result.lastrowid
        
    return {
        "ok": True,
        "receipt_id": receipt_id,
        "terminal_id": payload.terminal_id
    }


# -----------------------------
# Phase 2 (Legacy) Tap + Claim
# -----------------------------
@app.get("/m/{merchant_id}", response_class=HTMLResponse)
def tap_page_legacy(merchant_id: str):
    body = f"""
    <section class="card">
      <h1>Legacy Tap</h1>
      <p class="muted">Merchant: <b>{merchant_id}</b></p>
      <p>Your Vault works with no account. Add email if you want a copy.</p>
      <form method="post" action="/m/{merchant_id}/claim">
        <input type="hidden" name="device_id" id="device_id" />
        <input type="email" name="email" placeholder="optional@email.com" />
        <button class="btn" type="submit">Continue</button>
      </form>
      <div class="actions">
        <a class="btn-secondary" href="/v">Open My Vault</a>
      </div>
    </section>

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
    """
    return render_page("Legacy Tap", body)


@app.post("/m/{merchant_id}/claim", response_class=HTMLResponse)
def claim_email_legacy(
    merchant_id: str,
    device_id: str = Form(...),
    email: str = Form(""),
):
    created_at = _utcnow()

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

    body = f"""
    <section class="card">
      <h1>✅ Linked (Legacy)</h1>
      <p class="muted">Merchant: <b>{merchant_id}</b></p>
      <p>Device ID: <code>{device_id}</code></p>
      <p>Email copy: <b>{email if email else "(none)"}</b></p>
      <div class="actions">
        <a class="btn" href="/v">Open my Vault</a>
        <a class="btn-secondary" href="/pos/{merchant_id}">Go to POS</a>
      </div>
    </section>
    """
    return render_page("Linked", body)


# -----------------------------
# Phase 3 (Option C) Terminal Tap + Claim
# -----------------------------
@app.get("/t/{terminal_id}", response_class=HTMLResponse)
def terminal_tap_page(terminal_id: str):
    body = f"""
    <section class="card">
      <h1>Terminal Tap</h1>
      <p class="muted">Terminal: <b>{terminal_id}</b></p>
      <p>POS creates a paid receipt first, then tap here to claim it into your Vault.</p>

      <form method="post" action="/t/{terminal_id}/claim">
        <input type="hidden" name="device_id" id="device_id" />
        <input type="email" name="email" placeholder="optional@email.com" />
        <button class="btn" type="submit">Claim receipt</button>
      </form>

      <div class="actions">
        <a class="btn-secondary" href="/v">Open My Vault</a>
      </div>
    </section>

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
    """
    return render_page("Terminal Tap", body)


@app.post("/t/{terminal_id}/claim", response_class=HTMLResponse)
def terminal_claim_latest_receipt(
    terminal_id: str,
    device_id: str = Form(...),
    email: str = Form(""),
):
    now = _utcnow()

    with engine.begin() as conn:
        # Find latest PAID but unclaimed receipt for that terminal
        receipt = conn.execute(
            text(
                """
                SELECT id, merchant_id, total_cents
                FROM receipts
                WHERE terminal_id = :t
                  AND status = 'PAID'
                  AND claimed_at IS NULL
                ORDER BY COALESCE(paid_at, created_at) DESC, id DESC
                LIMIT 1
                """
            ),
            {"t": terminal_id},
        ).fetchone()

        if not receipt:
            body = """
            <section class="card">
              <h1>No New Paid Receipt</h1>
              <p>Ask the merchant to mark a receipt as paid in POS first.</p>
              <div class="actions">
                <a class="btn-secondary" href="/v">Open My Vault</a>
              </div>
            </section>
            """
            return render_page("Claim", body)

        # Atomic claim: only succeeds if still unclaimed
        updated = conn.execute(
            text(
                """
                UPDATE receipts
                SET status = 'CLAIMED',
                    claimed_at = :now,
                    claimed_by_device_id = :d,
                    email = CASE
                        WHEN :e IS NOT NULL AND TRIM(:e) <> '' THEN :e
                        ELSE email
                    END,
                    updated_at = :now
                WHERE id = :id
                  AND status = 'PAID'
                  AND claimed_at IS NULL
                """
            ),
            {"now": now, "d": device_id, "e": email, "id": receipt.id},
        )

        if updated.rowcount != 1:
            body = """
            <section class="card">
              <h1>No New Paid Receipt</h1>
              <p>Someone already claimed it. Try again after a new payment.</p>
              <div class="actions">
                <a class="btn-secondary" href="/v">Open My Vault</a>
              </div>
            </section>
            """
            return render_page("Claim", body)

    # Optional email send AFTER successful claim (Phase 3 behavior)
    email_status = ""
    if email and email.strip():
        try:
            send_receipt_email(
                to_email=email.strip(),
                merchant_id=receipt.merchant_id or terminal_id,
                total_pkr=(receipt.total_cents // 100),
                receipt_id=receipt.id,
            )
            email_status = "<p>✅ Email sent</p>"
        except Exception as e:
            email_status = f"<p>⚠️ Email failed: {e}</p>"

    body = f"""
    <section class="card">
      <h1>✅ Claimed</h1>
      <p class="muted">Receipt ID: <b>{receipt.id}</b></p>
      {email_status}
      <div class="actions">
        <a class="btn" href="/r/{receipt.id}">Open receipt</a>
        <a class="btn-secondary" href="/v">Open my Vault</a>
      </div>
    </section>
    """
    return render_page("Claimed", body)


# -----------------------------
# POS (Merchant side)
# -----------------------------
@app.get("/pos/{merchant_id}", response_class=HTMLResponse)
def pos_screen(merchant_id: str):
    body = f"""
    <section class="card">
      <h1>Simulated POS</h1>
      <p class="muted">Merchant/Terminal: <b>{merchant_id}</b></p>

      <form method="post" action="/pos/{merchant_id}/paid">
        <label>Total (PKR): </label>
        <input type="number" name="total_pkr" value="1990" min="0" required />
        <button class="btn" type="submit">Mark Paid</button>
      </form>

      <div class="actions">
        <a class="btn-secondary" href="/t/{merchant_id}">Go to terminal tap (/t/{merchant_id})</a>
        <a class="btn-secondary" href="/debug/claims">claims</a>
      </div>
    </section>
    """
    return render_page("Simulated POS", body)


@app.post("/pos/{merchant_id}/paid", response_class=HTMLResponse)
def pos_paid(merchant_id: str, total_pkr: int = Form(...)):
    now = _utcnow()

    with engine.begin() as conn:
        # Phase 3: always create an unclaimed PAID receipt (Option C)
        receipt = conn.execute(
            text(
                """
                INSERT INTO receipts (
                    terminal_id,
                    merchant_id,
                    total_cents,
                    currency,
                    status,
                    created_at,
                    updated_at,
                    paid_at,
                    claimed_at,
                    claimed_by_device_id,
                    email,
                    items_json
                )
                VALUES (:terminal, :m, :t, 'PKR', 'PAID', :now, :now, :now, NULL, NULL, NULL, NULL)
                """
            ),
            {
                "terminal": merchant_id,
                "m": merchant_id,
                "t": total_pkr * 100,
                "now": now,
            },
        )
        receipt_id = receipt.lastrowid

        # Phase 2 legacy compatibility: if there IS a legacy claim, we still dual-write to sales.
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

        if claim:
            conn.execute(
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
                    "c": now,
                },
            )

    # Phase 3: email happens at terminal claim time, not POS time.
    email_hint = ""
    if claim and claim.email:
        email_hint = "<p>ℹ️ Legacy claim exists, but Phase 3 email is sent on /t/... claim.</p>"

    body = f"""
    <section class="card">
      <h1>✅ Paid recorded</h1>
      <p class="muted">Receipt ID: <b>{receipt_id}</b></p>
      {email_hint}
      <div class="actions">
        <a class="btn" href="/r/{receipt_id}">View receipt</a>
        <a class="btn-secondary" href="/t/{merchant_id}">Customer tap to claim (/t/{merchant_id})</a>
        <a class="btn-secondary" href="/v">Open Vault</a>
        <a class="btn-secondary" href="/pos/{merchant_id}">Back to POS</a>
      </div>
    </section>
    """
    return render_page("Paid recorded", body)


# -----------------------------
# Receipt page
# -----------------------------
@app.get("/r/{rid}", response_class=HTMLResponse)
def receipt_page(rid: int):
    with engine.begin() as conn:
        receipt = conn.execute(
            text(
                """
                SELECT id, terminal_id, merchant_id, total_cents, currency, status, created_at,
                       paid_at, claimed_at, claimed_by_device_id, email, items_json
                FROM receipts
                WHERE id = :id
                """
            ),
            {"id": rid},
        ).fetchone()

        sale = None
        if not receipt:
            # Legacy fallback
            sale = conn.execute(
                text(
                    """
                    SELECT id, merchant_id, email, device_id, total_cents, status, created_at
                    FROM sales
                    WHERE id = :id
                    """
                ),
                {"id": rid},
            ).fetchone()

    if not receipt and not sale:
        return render_page(
            "Not Found",
            """
            <section class="card">
              <h1>Receipt not found</h1>
              <p class="muted">The requested receipt could not be found or has been removed.</p>
              <div class="actions">
                <a class="btn-secondary" href="/v">Back to Vault</a>
              </div>
            </section>
            """
        )

    if receipt:
        total_pkr = receipt.total_cents / 100.0
        currency = (receipt.currency or "PKR").upper()
        device_id = receipt.claimed_by_device_id or ""
        email = receipt.email or ""
        merchant = receipt.merchant_id or receipt.terminal_id or "unknown"
        
        structured_html = ""
        if receipt.items_json:
            try:
                data = json.loads(receipt.items_json)
                
                # Metadata (date, cashier, payment method)
                meta_rows = ""
                if data.get("date"):
                    meta_rows += f"<li class='row'><small>Receipt Date</small> <span>{data['date']}</span></li>"
                if data.get("cashier"):
                    meta_rows += f"<li class='row'><small>Cashier</small> <span>{data['cashier']}</span></li>"
                if data.get("paymentMethod"):
                    meta_rows += f"<li class='row'><small>Payment Method</small> <span>{data['paymentMethod']}</span></li>"
                
                if meta_rows:
                    meta_rows = f"<ul class='clean meta' style='margin-bottom: 20px;'>{meta_rows}</ul>"
                
                # Item rows
                items_html = ""
                items = data.get("items", [])
                if items:
                    items_html += "<h3>Items</h3><ul class='clean' style='margin-bottom: 20px;'>"
                    for item in items:
                        qty = f"{item.get('qty')}x " if item.get('qty') else ""
                        name = item.get("name", "Unknown Item")
                        price_val = item.get("linePrice")
                        price_str = f" — {float(price_val):.2f} {currency}" if price_val is not None else ""
                        items_html += f"<li class='row'><span>{qty}<b>{name}</b></span> <small>{price_str}</small></li>"
                    items_html += "</ul>"
                
                # Totals
                totals_html = ""
                if data.get("subtotal") is not None:
                    totals_html += f"<li class='row'><small>Subtotal</small> <span>{float(data['subtotal']):.2f} {currency}</span></li>"
                if data.get("discount") is not None:
                    totals_html += f"<li class='row'><small>Discount</small> <span>{float(data['discount']):.2f} {currency}</span></li>"
                if data.get("tax") is not None:
                    totals_html += f"<li class='row'><small>Tax</small> <span>{float(data['tax']):.2f} {currency}</span></li>"
                
                if totals_html:
                    totals_html = f"<ul class='clean meta' style='margin-bottom: 20px;'>{totals_html}</ul>"
                
                structured_html = f"{meta_rows}{items_html}{totals_html}"
            except Exception:
                structured_html = "<div class='meta' style='margin-bottom: 20px;'><p class='muted'><i>Structured receipt details unavailable.</i></p></div>"

        body = f"""
        <section class="card">
          <div class="row" style="border-bottom: none; padding-bottom: 0;">
            <div class="muted">Receipt #{receipt.id}</div>
            {status_pill(receipt.status)}
          </div>
          
          <h1 style="margin-top: 8px;">{merchant}</h1>
          <div class="amount">{total_pkr:.2f} <span style="font-size: 0.4em; color: var(--muted); vertical-align: middle;">{currency}</span></div>

          {structured_html}

          <h3>System Log</h3>
          <ul class="clean meta">
            <li class="row"><small>Created (UTC)</small> <span>{receipt.created_at}</span></li>
            <li class="row"><small>Paid at (UTC)</small> <span>{receipt.paid_at or "(n/a)"}</span></li>
            <li class="row"><small>Claimed at (UTC)</small> <span>{receipt.claimed_at or "(not claimed yet)"}</span></li>
          </ul>

          <div class="meta">
            <p><small>Vault Device ID:</small><br/><code>{device_id or "Unclaimed"}</code></p>
            <p><small>Email copy:</small><br/><b>{email if email else "(none)"}</b></p>
          </div>

          <div class="actions" style="margin-top: 24px;">
            <a class="btn-secondary" href="/v">Back to Vault</a>
          </div>
        </section>
        """
        return render_page(f"Receipt #{receipt.id}", body)

    # Legacy sale formatting
    total_pkr = sale.total_cents / 100.0
    body = f"""
    <section class="card">
      <div class="row" style="border-bottom: none; padding-bottom: 0;">
        <div class="muted">Legacy Receipt #{sale.id}</div>
        {status_pill(sale.status)}
      </div>
      
      <h1 style="margin-top: 8px;">{sale.merchant_id}</h1>
      <div class="amount">{total_pkr:.2f} <span style="font-size: 0.4em; color: var(--muted); vertical-align: middle;">PKR</span></div>

      <ul class="clean meta">
        <li class="row"><small>Created (UTC)</small> <span>{sale.created_at}</span></li>
      </ul>

      <div class="meta">
        <p><small>Vault Device ID:</small><br/><code>{sale.device_id or "Unclaimed"}</code></p>
        <p><small>Email copy:</small><br/><b>{sale.email if sale.email else "(none)"}</b></p>
      </div>

      <div class="actions" style="margin-top: 24px;">
        <a class="btn-secondary" href="/v">Back to Vault</a>
      </div>
    </section>
    """
    return render_page(f"Receipt #{sale.id}", body)


# -----------------------------
# Vault (Consumer side)
# -----------------------------
@app.get("/v", response_class=HTMLResponse)
def vault_page():
    body = """
    <section class="card">
      <h1>My RCPT Vault</h1>
      <p class="muted">This Vault is tied to your device (no account).</p>

      <div id="out">Loading…</div>

      <div class="actions">
        <a class="btn-secondary" href="/t/test">Terminal demo (/t/test)</a>
        <a class="btn-secondary" href="/m/test">Legacy demo (/m/test)</a>
      </div>

      <script>
        (async function () {
          let id = localStorage.getItem("rcpt_device_id");
          if (!id) {
            id = crypto.randomUUID();
            localStorage.setItem("rcpt_device_id", id);
          }

          const fmt = (v) => {
            const d = new Date(v);
            return isNaN(d.getTime()) ? String(v ?? "") : d.toLocaleString();
          };

          try {
            const res = await fetch(`/api/vault/${id}`);
            if (!res.ok) {
              document.getElementById("out").innerHTML = `
                <p><b>Could not load receipts.</b></p>
                <p class="muted">Please try again in a moment.</p>
                <p><code>Device ID:</code> ${id}</p>
              `;
              return;
            }

            const data = await res.json();

            const receipts = Array.isArray(data.receipts) ? data.receipts : [];

            if (receipts.length === 0) {
              document.getElementById("out").innerHTML = `
                <p><b>No receipts yet.</b></p>
                <p>Try: /pos/test -> Mark paid, then /t/test -> Claim.</p>
                <p><code>Device ID:</code> ${id}</p>
              `;
              return;
            }

            const items = receipts.map(r => `
            <li class="row">
              <a href="/r/${r.id}">Receipt #${r.id}</a>
              — <b>${r.merchant_id}</b>
              — ${r.total_pkr} PKR
              — <small>${fmt(r.when)}</small>
              ${r.source ? ` — <small>(${r.source})</small>` : ``}
            </li>
          `).join("");

          document.getElementById("out").innerHTML = `
            <p><code>Device ID:</code> ${data.device_id}</p>
            <ul class="clean">${items}</ul>
          `;
          } catch (err) {
            document.getElementById("out").innerHTML = `
              <p><b>Could not load receipts.</b></p>
              <p class="muted">Please check your connection and try again.</p>
              <p><code>Device ID:</code> ${id}</p>
              <p class="muted">${String(err)}</p>
            `;
          }
        })();
      </script>
    </section>
    """
    return render_page("My Vault", body)


@app.get("/api/vault/{device_id}")
def vault_api(device_id: str):
    with engine.begin() as conn:
        # Phase 3: claimed receipts
        receipt_rows = conn.execute(
            text(
                """
                SELECT id, merchant_id, total_cents, created_at, claimed_at
                FROM receipts
                WHERE claimed_by_device_id = :d
                ORDER BY id DESC
                """
            ),
            {"d": device_id},
        ).fetchall()

        # Legacy: sales rows for compatibility
        sales_rows = conn.execute(
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

    seen = {r.id for r in receipt_rows}
    combined = list(receipt_rows) + [s for s in sales_rows if s.id not in seen]

    receipts = []
    for r in combined:
        # receipts rows have claimed_at; sales rows don't
        when = getattr(r, "claimed_at", None) or r.created_at
        source = "receipts" if hasattr(r, "claimed_at") else "legacy-sales"

        receipts.append(
            {
                "id": r.id,
                "merchant_id": r.merchant_id,
                "total_pkr": r.total_cents // 100,
                "when": when,
                "source": source,
            }
        )

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