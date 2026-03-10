import { z } from "zod";

export const vaultReceiptSchema = z.object({
  id: z.number(),
  merchant_id: z.string(),
  total_pkr: z.number(),
  when: z.string(),
  source: z.string(),
});

export const vaultResponseSchema = z.object({
  device_id: z.string(),
  receipts: z.array(vaultReceiptSchema),
});

export const claimRequestSchema = z.object({
  device_id: z.string(),
  terminal_id: z.string(),
  email: z.string().optional(),
});

export const claimResponseSchema = z.object({
  success: z.boolean(),
  receipt_id: z.number().optional(),
  device_id: z.string().optional(),
  terminal_id: z.string().optional(),
  message: z.string().optional(),
});

export const receiptItemDetailSchema = z.object({
  name: z.string(),
  qty: z.number(),
  unitPrice: z.number().nullable().optional(),
  linePrice: z.number(),
});

export const receiptDetailSchema = z.object({
  id: z.number(),
  terminal_id: z.string().nullable().optional(),
  merchant_id: z.string(),
  currency: z.string().nullable().optional(),
  status: z.string().nullable().optional(),
  created_at: z.string().nullable().optional(),
  paid_at: z.string().nullable().optional(),
  claimed_at: z.string().nullable().optional(),
  claimed_by_device_id: z.string().nullable().optional(),
  email: z.string().nullable().optional(),
  date: z.string().nullable().optional(),
  cashier: z.string().nullable().optional(),
  paymentMethod: z.string().nullable().optional(),
  subtotal: z.number().nullable().optional(),
  discount: z.number().nullable().optional(),
  tax: z.number().nullable().optional(),
  total: z.number().nullable().optional(),
  items: z.array(receiptItemDetailSchema).optional().default([]),
  is_legacy: z.boolean().nullable().optional(),
});

export type VaultReceipt = z.infer<typeof vaultReceiptSchema>;
export type VaultResponse = z.infer<typeof vaultResponseSchema>;
export type ClaimRequest = z.infer<typeof claimRequestSchema>;
export type ClaimResponse = z.infer<typeof claimResponseSchema>;
export type ReceiptItemDetail = z.infer<typeof receiptItemDetailSchema>;
export type ReceiptDetail = z.infer<typeof receiptDetailSchema>;
