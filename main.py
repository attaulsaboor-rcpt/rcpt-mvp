import os
from datetime import datetime

import resend
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse
from sqlalchemy import create_engine, text

app = FastAPI()

# SQLite DB in project folder
engine = create_engine("sqlite:///rcpt.db", connect_args={"check_same_thread": False})


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
    return """
    <html><body>
      <h1>Hello RCPT</h1>
      <ul>
        <li><a href="/m/test">Legacy tap page: /m/test</a></li>
        <li><a href="/t/test">Terminal tap page: /t/test</a></li>
        <li><a href="/pos/test">POS page: /pos/test</a></li>
        <li><a href="/v">Vault: /v</a></li>
      </ul>
    </body></html>
    """


# -----------------------------
# Phase 2 (Legacy) Tap + Claim
# -----------------------------
@app.get("/m/{merchant_id}", response_class=HTMLResponse)
def tap_page_legacy(merchant_id: str):
    return f"""
    <html><body>
      <h1>RCPT (Legacy Tap)</h1>
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

    return f"""
    <html><body>
      <h1>✅ Linked (Legacy)</h1>
      <p>Merchant: <b>{merchant_id}</b></p>
      <p>Device ID: <code>{device_id}</code></p>
      <p>Email copy: <b>{email if email else "(none)"}</b></p>
      <p><a href="/v">Open my Vault</a></p>
      <p><a href="/pos/{merchant_id}">Go to POS</a></p>
    </body></html>
    """


# -----------------------------
# Phase 3 (Option C) Terminal Tap + Claim
# -----------------------------
@app.get("/t/{terminal_id}", response_class=HTMLResponse)
def terminal_tap_page(terminal_id: str):
    return f"""
    <html><body>
      <h1>RCPT (Terminal Tap)</h1>
      <p>Terminal: <b>{terminal_id}</b></p>

      <p>
        This is the Phase 3 flow: POS creates a PAID receipt first, then you tap to claim it into your Vault.
      </p>

      <form method="post" action="/t/{terminal_id}/claim">
        <input type="hidden" name="device_id" id="device_id" />
        <input type="email" name="email" placeholder="optional@email.com" />
        <button type="submit">Claim latest paid receipt</button>
      </form>

      <p style="margin-top:16px;">
        <a href="/v">Open my Vault</a>
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
            return """
            <html><body>
              <h1>No new paid receipt to claim</h1>
              <p>Ask the merchant to mark a receipt as paid in the POS first.</p>
              <p><a href="/v">Open my Vault</a></p>
            </body></html>
            """

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
            return """
            <html><body>
              <h1>No new paid receipt to claim</h1>
              <p>Someone already claimed it (or it changed). Try again after a new payment.</p>
              <p><a href="/v">Open my Vault</a></p>
            </body></html>
            """

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

    return f"""
    <html><body>
      <h1>✅ Claimed</h1>
      <p>Receipt ID: <b>{receipt.id}</b></p>
      <p><a href="/r/{receipt.id}">Open receipt</a></p>
      <p><a href="/v">Open my Vault</a></p>
      {email_status}
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
      <p>Merchant/Terminal: <b>{merchant_id}</b></p>

      <form method="post" action="/pos/{merchant_id}/paid">
        <label>Total (PKR): </label>
        <input type="number" name="total_pkr" value="1990" min="0" required />
        <button type="submit">Mark Paid</button>
      </form>

      <p style="margin-top:16px;">
        <a href="/t/{merchant_id}">Go to terminal tap (/t/{merchant_id})</a><br/>
        Debug: <a href="/debug/claims">claims</a>
      </p>
    </body></html>
    """


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

    return f"""
    <html><body>
      <h1>✅ Paid recorded</h1>
      <p>Receipt ID: <b>{receipt_id}</b></p>
      {email_hint}
      <p><a href="/r/{receipt_id}">View receipt</a></p>
      <p><a href="/t/{merchant_id}">Customer tap to claim (/t/{merchant_id})</a></p>
      <p><a href="/v">Open Vault</a></p>
      <p><a href="/pos/{merchant_id}">Back to POS</a></p>
    </body></html>
    """


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
                       paid_at, claimed_at, claimed_by_device_id, email
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
        return "<h1>Receipt not found</h1>"

    if receipt:
        total_pkr = receipt.total_cents // 100
        currency = (receipt.currency or "PKR").upper()
        device_id = receipt.claimed_by_device_id or ""
        email = receipt.email or ""
        merchant = receipt.merchant_id or receipt.terminal_id or "unknown"

        return f"""
        <html><body>
          <h1>RCPT Receipt (Phase 3)</h1>
          <p><b>Receipt ID:</b> {receipt.id}</p>
          <p><b>Merchant/Terminal:</b> {merchant}</p>
          <p><b>Status:</b> {receipt.status}</p>
          <p><b>Total:</b> {total_pkr} {currency}</p>
          <p><b>Created (UTC):</b> {receipt.created_at}</p>
          <p><b>Paid at (UTC):</b> {receipt.paid_at or "(n/a)"}</p>
          <p><b>Claimed at (UTC):</b> {receipt.claimed_at or "(not claimed yet)"}</p>
          <hr/>
          <p><b>Vault Device ID:</b> <code>{device_id}</code></p>
          <p><b>Email copy:</b> {email if email else "(none)"}</p>
          <p><a href="/v">Back to Vault</a></p>
        </body></html>
        """

    # Legacy sale
    total_pkr = sale.total_cents // 100
    return f"""
    <html><body>
      <h1>RCPT Receipt (Legacy)</h1>
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
    return """
    <html><body>
      <h1>My RCPT Vault</h1>
      <p>This Vault is tied to your device (no account).</p>

      <div id="out">Loading…</div>

      <p style="margin-top:16px;">
        <a href="/t/test">Terminal demo (/t/test)</a> |
        <a href="/m/test">Legacy demo (/m/test)</a>
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
              <p>Try: /pos/test -> Mark paid, then /t/test -> Claim.</p>
              <p><code>Device ID:</code> ${id}</p>
            `;
            return;
          }

          const items = data.receipts.map(r => `
            <li>
              <a href="/r/${r.id}">Receipt #${r.id}</a>
              — <b>${r.merchant_id}</b>
              — ${r.total_pkr} PKR
              — <small>${r.when}</small>
              ${r.source ? ` — <small>(${r.source})</small>` : ``}
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