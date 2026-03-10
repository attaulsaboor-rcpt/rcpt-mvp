import { type VaultReceipt, type ClaimResponse, type ReceiptDetail, receiptDetailSchema } from "@shared/schema";

export const BASE_URL = "https://rcpt.digital";

export type { ClaimResponse };

async function parseErrorMessage(res: Response): Promise<string> {
  try {
    const body = await res.json();
    if (res.status === 422) {
      return "Invalid request. Please try again.";
    }
    if (body?.message) {
      return body.message;
    }
    if (body?.detail) {
      if (typeof body.detail === "string") return body.detail;
      if (Array.isArray(body.detail) && body.detail[0]?.msg) {
        return body.detail[0].msg;
      }
    }
  } catch {
    // ignore json parse failure
  }
  return `Request failed (${res.status})`;
}

export async function fetchVault(deviceId: string): Promise<VaultReceipt[]> {
  const res = await fetch(`${BASE_URL}/api/vault/${deviceId}`);
  if (!res.ok) {
    const msg = await parseErrorMessage(res);
    throw new Error(msg);
  }
  const data = await res.json();
  return data.receipts ?? [];
}

export async function fetchReceipt(receiptId: number): Promise<ReceiptDetail> {
  const res = await fetch(`${BASE_URL}/api/receipts/${receiptId}`);
  if (!res.ok) {
    const msg = await parseErrorMessage(res);
    throw new Error(msg);
  }
  const data = await res.json();
  return receiptDetailSchema.parse(data);
}

export async function claimReceipt(
  deviceId: string,
  terminalId: string,
  email?: string
): Promise<ClaimResponse> {
  const body: Record<string, string> = {
    device_id: deviceId,
    terminal_id: terminalId,
  };
  if (email) body.email = email;

  const res = await fetch(`${BASE_URL}/api/claim`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const msg = await parseErrorMessage(res);
    throw new Error(msg);
  }

  return res.json();
}
