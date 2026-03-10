import type { Express } from "express";
import { createServer, type Server } from "http";
import { storage, MemStorage } from "./storage";
import { claimRequestSchema } from "@shared/schema";

export async function registerRoutes(
  httpServer: Server,
  app: Express
): Promise<Server> {

  app.get("/api/vault/:device_id", async (req, res) => {
    try {
      const { device_id } = req.params;
      const receipts = await storage.getReceiptsByDevice(device_id);
      res.json(receipts);
    } catch (err) {
      res.status(500).json({ error: "Failed to fetch vault" });
    }
  });

  app.get("/api/receipt/:receipt_id", async (req, res) => {
    try {
      const { receipt_id } = req.params;
      const receipt = await storage.getReceiptById(receipt_id);
      if (!receipt) {
        return res.status(404).json({ error: "Receipt not found" });
      }
      res.json(receipt);
    } catch (err) {
      res.status(500).json({ error: "Failed to fetch receipt" });
    }
  });

  app.post("/api/claim", async (req, res) => {
    try {
      const parsed = claimRequestSchema.safeParse(req.body);
      if (!parsed.success) {
        return res.status(400).json({ error: "Invalid request" });
      }
      const result = await storage.claimReceipt(parsed.data);
      res.json(result);
    } catch (err) {
      res.status(500).json({ error: "Failed to claim receipt" });
    }
  });

  app.get("/api/pending", async (req, res) => {
    try {
      const mem = storage as MemStorage;
      const pending = mem.getPendingReceipt();
      res.json(pending || null);
    } catch (err) {
      res.status(500).json({ error: "Failed to fetch pending receipt" });
    }
  });

  return httpServer;
}
