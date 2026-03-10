# RCPT Vault — Developer Notes

## Product Context

RCPT Vault is the consumer-facing web app for the RCPT digital receipt ecosystem. Customers tap an NFC tag at a POS terminal after checkout; the tag's URL encodes a terminal ID which the browser uses to call the RCPT backend and claim the receipt into the device's personal vault.

The app is a mobile-first SPA — designed to run in a phone browser after an NFC tap. There is no login, no account creation. Identity is entirely device-based (UUID in localStorage).

---

## Tech Stack

| Layer | Choice |
|---|---|
| Framework | React 18 + TypeScript |
| Build | Vite |
| Routing | Wouter |
| Data fetching | TanStack Query v5 |
| Styling | Tailwind CSS + shadcn/ui |
| Icons | lucide-react |
| Font | Plus Jakarta Sans (loaded via index.css) |
| Schema / validation | Zod (shared/schema.ts) |
| Local server (vestigial) | Express + tsx |

---

## Live Backend Contract

All real data flows **browser → https://rcpt.digital** directly. There is no backend proxy.

### GET /api/vault/{device_id}

Fetches all receipts claimed by a device. Returns a **wrapper object**, not a bare array:

```json
{
  "device_id": "550e8400-e29b-41d4-a716-446655440000",
  "receipts": [
    {
      "id": 1,
      "merchant_id": "Atlas Bistro",
      "total_pkr": 1647.00,
      "when": "2026-03-08T18:24:00",
      "source": "receipts"
    }
  ]
}
```

These are **thin records** — no line items, tax breakdown, cashier, or payment method. `fetchVault()` unwraps `.receipts` before returning.

### GET /api/receipts/{receipt_id}

Fetches full rich receipt detail for a single receipt by numeric ID.

```json
{
  "id": 1,
  "terminal_id": "term_abc123",
  "merchant_id": "Atlas Bistro",
  "currency": "PKR",
  "status": "claimed",
  "created_at": "2026-03-08T18:24:00",
  "paid_at": "2026-03-08T18:24:05",
  "claimed_at": "2026-03-08T18:25:00",
  "claimed_by_device_id": "...",
  "email": "user@example.com",
  "date": "2026-03-08",
  "cashier": "Register 2",
  "paymentMethod": "Visa •••• 4821",
  "subtotal": 1420.00,
  "discount": 0,
  "tax": 227.00,
  "total": 1647.00,
  "items": [
    { "name": "Truffle Risotto", "qty": 1, "unitPrice": 1100.00, "linePrice": 1100.00 },
    { "name": "Sparkling Water", "qty": 2, "unitPrice": 160.00, "linePrice": 320.00 }
  ],
  "is_legacy": false
}
```

All fields except `id` and `merchant_id` are optional/nullable. `items` defaults to `[]`. The response is validated against `receiptDetailSchema` in Zod.

### POST /api/claim

Claims a receipt for the device at a given terminal.

**Request:**
```json
{
  "device_id": "550e8400-e29b-41d4-a716-446655440000",
  "terminal_id": "term_abc123",
  "email": "optional@example.com"
}
```
- `device_id` — required
- `terminal_id` — required
- `email` — optional, not currently exposed in the UI

**Success (200):**
```json
{ "success": true, "receipt_id": 42, "device_id": "...", "terminal_id": "...", "message": "Receipt claimed successfully" }
```

**Business-logic errors (400 / 404 / 409):**
```json
{ "success": false, "message": "No pending receipt at this terminal" }
```

**FastAPI validation errors (422):** surfaced as "Invalid request. Please try again."

**Network failures:** surfaced as "Request failed (status)" or caught error message.

---

## Device Identity

```
localStorage key: "rcpt_device_id"
value: crypto.randomUUID()
```

Generated once on first visit, persisted forever. Clearing localStorage resets the device identity and empties the vault view (backend retains data under the old UUID).

**`client/src/lib/deviceId.ts`** — lazy-initialises and returns the device ID. Called at the top of any component that needs it.

---

## Data Flow

### Vault Fetch

```
VaultPage mounts
  → getDeviceId()
  → useQuery(["vault", deviceId])
      → fetchVault(deviceId)
          → GET https://rcpt.digital/api/vault/{deviceId}
          → unwrap data.receipts
          → return VaultReceipt[]
  → render ReceiptCard list
```

TanStack Query caches under `["vault", deviceId]` with `staleTime: Infinity`. Only re-fetches after a successful claim invalidates the cache.

### Claim Flow

```
User taps "Tap" button on VaultPage
  → navigate("/t/term_demo_001")

TerminalClaimPage mounts
  → terminalId = params.terminalId
  → deviceId = getDeviceId()
  → setTimeout(runClaim, 1600)   // 1.6s connecting animation

runClaim()
  → step = "claiming"
  → claimReceipt(deviceId, terminalId)
      → POST https://rcpt.digital/api/claim
  → on success:
      queryClient.invalidateQueries(["vault", deviceId])
      step = "success"
  → on error:
      step = "error", errorMessage = err.message
```

### Receipt Detail Fetch

```
ReceiptDetailPage mounts with params.id (string)
  → receiptId = Number(params.id)
  → useQuery(["receipt", receiptId])
      → fetchReceipt(receiptId)
          → GET https://rcpt.digital/api/receipts/{receiptId}
          → validate with receiptDetailSchema.parse()
          → return ReceiptDetail
  → render rich detail view
```

The detail page now fetches independently — it does **not** read from the vault list cache. This means it works even on a cold load or direct URL navigation.

---

## TanStack Query Key Schema

| Key | Stores | Invalidated by |
|---|---|---|
| `["vault", deviceId]` | `VaultReceipt[]` from vault API | Successful claim |
| `["receipt", receiptId]` | `ReceiptDetail` from receipt detail API | Never — stale forever |

**Query client config** (`client/src/lib/queryClient.ts`):
- `staleTime: Infinity` — data never goes stale automatically
- `refetchOnWindowFocus: false`
- `retry: false` — fail fast, surface errors immediately

---

## Type System (`shared/schema.ts`)

```typescript
// Thin record from vault list
VaultReceipt = { id: number, merchant_id, total_pkr, when, source }

// Vault API wrapper
VaultResponse = { device_id, receipts: VaultReceipt[] }

// Single item in a rich receipt
ReceiptItemDetail = { name, qty, unitPrice?, linePrice }

// Full rich receipt from /api/receipts/:id
ReceiptDetail = {
  id: number, merchant_id: string,
  terminal_id?, currency?, status?,
  created_at?, paid_at?, claimed_at?, claimed_by_device_id?,
  email?, date?, cashier?, paymentMethod?,
  subtotal?, discount?, tax?, total?,
  items: ReceiptItemDetail[],   // defaults to []
  is_legacy?
}

// Claim request body
ClaimRequest = { device_id, terminal_id, email? }

// Claim API response
ClaimResponse = { success, receipt_id?, device_id?, terminal_id?, message? }
```

All monetary and timestamp fields on `ReceiptDetail` are `nullable | optional` — the detail page guards every one before rendering.

---

## File-by-File Breakdown

### `shared/schema.ts`
Single source of truth for all data contracts. Zod schemas for vault receipts, rich receipt detail (with items), claim request, and claim response. TypeScript types inferred via `z.infer<>`.

### `client/src/lib/rcptApi.ts`
All calls to `https://rcpt.digital`. Three public functions:
- `fetchVault(deviceId)` → `Promise<VaultReceipt[]>` — unwraps `{ receipts }` wrapper
- `fetchReceipt(receiptId)` → `Promise<ReceiptDetail>` — validates response with Zod
- `claimReceipt(deviceId, terminalId, email?)` → `Promise<ClaimResponse>`

Error parsing: 422 → generic message; 400/404/409 → `body.message`; network → status code string.

### `client/src/lib/deviceId.ts`
`getDeviceId()` — reads `rcpt_device_id` from localStorage, generates and saves a UUID if absent.

### `client/src/lib/format.ts`
- `formatDate/DateTime/Time(dateStr)` — locale date formatting
- `getMerchantInitials(name)` — splits on whitespace, first letter of first two words
- `getMerchantAvatarBg(category?)` — Tailwind bg class; falls back to `bg-primary` (vault API has no category field)
- `getMerchantCategoryStyle(category?)` — badge color; currently unused in thin-record UI
- `formatCurrency(amount)` — USD formatter; **not used by detail page** (detail page uses its own `formatAmount(value, currency)` helper that reads the currency field from the API)

### `client/src/App.tsx`
Three routes:

| Path | Component |
|---|---|
| `/` | `VaultPage` |
| `/receipt/:id` | `ReceiptDetailPage` |
| `/t/:terminalId` | `TerminalClaimPage` |

### `client/src/pages/VaultPage.tsx`
Receipt list with search, merchant filter, and sort. All filtering/sorting is client-side over the `VaultReceipt[]` cache. "Tap" button and empty state CTA both navigate to `/t/term_demo_001`.

### `client/src/pages/TerminalClaimPage.tsx`
Single claim entry point. Reads `terminalId` from route params, fires claim after 1.6s NFC animation. Four UI states: `connecting → claiming → success | error`. Invalidates vault cache on success.

Real NFC: when a physical RCPT tag is tapped, the tag URL (e.g. `https://rcpt.digital/t/term_abc123`) navigates the browser here with the real terminal ID — identical flow.

### `client/src/pages/ReceiptDetailPage.tsx`
Fetches rich receipt from `GET /api/receipts/:id` via `fetchReceipt()`. Query key: `["receipt", receiptId]`. Currency comes from `receipt.currency` (falls back to "PKR" if absent). Sections rendered conditionally:
- Merchant header + status pill
- Hero total + date
- Meta grid: date, time, ID, cashier?, paymentMethod?, email?
- Items table (only if `items.length > 0`)
- Totals breakdown (subtotal, discount if > 0, tax if > 0)
- Grand total row
- Verified watermark footer

Legacy/sparse receipts (empty items, missing breakdowns) render cleanly — no crashes, no hardcoded "unavailable" banners.

### `client/src/components/ReceiptCard.tsx`
Thin record card: merchant initials avatar, `merchant_id`, formatted `when`, formatted `total_pkr`. No items, no status badge.

### `client/src/components/EmptyState.tsx`
Empty vault CTA — `onSimulate` prop wired to `navigate("/t/term_demo_001")` in VaultPage.

### `server/storage.ts` + `server/routes.ts`
**Vestigial stub.** Express boots so Vite can be served through it; all real data goes to `https://rcpt.digital`. Do not add vault or claim logic here.

---

## Design System

- **Font**: Plus Jakarta Sans
- **Colors**: HSL CSS variables in `index.css` (`:root` + `.dark`)
- **Cards**: `bg-card border border-card-border rounded-xl` (list) / `rounded-2xl` (detail)
- **Elevation**: `hover-elevate` / `active-elevate-2` Tailwind utilities on interactive cards
- **Container**: `max-w-lg mx-auto px-4` on all pages
- **Components**: shadcn/ui — Button, Input, Skeleton, Separator, DropdownMenu, Toaster

---

## Demo Usage

1. Open the app at `/`
2. Click **Tap** (header) or **Simulate NFC Tap** (empty state) → lands at `/t/term_demo_001`
3. 1.6s NFC animation → claim fires against live backend
4. Success: vault cache invalidates, "View My Vault" returns to `/`
5. Click any receipt card → `/receipt/:id` → full rich detail loads from `GET /api/receipts/:id`

To navigate directly: `/t/<any-terminal-id>` to test any terminal; `/receipt/<id>` to deep-link to any receipt.

To reset device: DevTools → Application → Local Storage → delete `rcpt_device_id`.

---

## Known Gaps & TODOs

| Gap | Impact | Fix |
|---|---|---|
| CORS not configured for Replit dev/deployed domain | API calls fail in browser preview | Backend adds `Access-Control-Allow-Origin` for Replit `.replit.app` domain |
| `formatCurrency()` in format.ts uses USD | Not used by detail page, but may mislead future devs | Update or remove — detail page uses its own `formatAmount(value, currency)` |
| `getMerchantAvatarBg()` always falls back to `bg-primary` | All avatars same colour | Either hash `merchant_id` to pick from a palette, or wait for API to return category |
| `email` field not exposed in claim UI | Can't capture email at claim time | Add optional email input to `TerminalClaimPage` before `runClaim` fires |
| Vestigial Express routes (`/api/pending`, `/api/receipt/:id`) | Dead code, no behaviour | Remove when convenient |

---

## Extension Guide

### Adding email capture to claim flow
1. Add optional email `<Input>` to `TerminalClaimPage.tsx` shown before the 1.6s animation starts
2. Store in local state, pass as third arg to `claimReceipt(deviceId, terminalId, email)`
3. No other changes needed — API already sends it when present

### Real NFC hardware (Web NFC API)
Physical tags encode a URL like `https://rcpt.digital/t/term_abc123`. Android Chrome navigates there automatically on tap — `TerminalClaimPage` handles it identically. For in-app NFC scanning without leaving the page, use [`NDEFReader`](https://developer.mozilla.org/en-US/docs/Web/API/Web_NFC_API) (Android Chrome 89+, not available on iOS).

### Merchant avatar colours
`getMerchantAvatarBg()` in `format.ts` takes an optional `category` string. Once the vault or detail API returns a category, pass it in; or replace with a deterministic hash of `merchant_id` to pick from a fixed colour palette.
