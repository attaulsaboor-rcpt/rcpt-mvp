import { type ClaimRequest, type VaultReceipt } from "@shared/schema";

export interface IStorage {
  getReceiptsByDevice(deviceId: string): Promise<VaultReceipt[]>;
  getReceiptById(receiptId: string): Promise<VaultReceipt | undefined>;
  claimReceipt(req: ClaimRequest): Promise<{ success: boolean; message: string }>;
}

export class MemStorage implements IStorage {
  async getReceiptsByDevice(_deviceId: string): Promise<VaultReceipt[]> {
    return [];
  }

  async getReceiptById(_receiptId: string): Promise<VaultReceipt | undefined> {
    return undefined;
  }

  async claimReceipt(_req: ClaimRequest): Promise<{ success: boolean; message: string }> {
    return { success: false, message: "Use the live backend at https://rcpt.digital" };
  }

  getPendingReceipt(): undefined {
    return undefined;
  }
}

export const storage = new MemStorage();
