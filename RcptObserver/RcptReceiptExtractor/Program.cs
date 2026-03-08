using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text.RegularExpressions;

namespace RcptReceiptExtractor
{
    class Program
    {
        static void Main(string[] args)
        {
            Console.WriteLine("========================================");
            Console.WriteLine("RCPT Bridge - Receipt Extractor v0.3");
            Console.WriteLine("========================================\n");

            // 1. Check for arguments
            if (args.Length == 0)
            {
                Console.WriteLine("Usage: dotnet run -- <path_to_cleaned_receipt.txt>");
                Console.WriteLine("Example: dotnet run -- receipt_20260308_032330_520_cleaned.txt");
                return;
            }

            string filePath = args[0];

            // 2. Check if file exists
            if (!File.Exists(filePath))
            {
                Console.WriteLine($"[ERROR] File not found: {filePath}");
                return;
            }

            try
            {
                // 3. Read lines and convert to List<string>
                Console.WriteLine($"--- INPUT: LOADED FROM {filePath} ---");
                List<string> inputLines = File.ReadAllLines(filePath).ToList();

                // Echo the loaded lines (optional, good for debugging the pipeline)
                foreach (var line in inputLines)
                {
                    Console.WriteLine(line);
                }
                
                Console.WriteLine("\n--- EXECUTING EXTRACTION ---");

                // 4. Extract
                var extractor = new ReceiptExtractor();
                ReceiptExtractionResult result = extractor.Extract(inputLines);

                // 5. Print Results
                PrintReceipt(result.Receipt);

                // 6. Print Unclassified Lines
                Console.WriteLine("\n--- UNCLASSIFIED LINES (DEBUG) ---");
                if (!result.UnclassifiedLines.Any())
                {
                    Console.WriteLine("(None)");
                }
                else
                {
                    foreach (var uLine in result.UnclassifiedLines)
                    {
                        Console.WriteLine($"- {uLine}");
                    }
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[FATAL ERROR] Failed to process file: {ex.Message}");
            }
        }

        private static void PrintReceipt(Receipt r)
        {
            Console.WriteLine("--- STRUCTURED RECEIPT OBJECT ---");
            Console.WriteLine($"Merchant       : {r.Merchant ?? "Unknown"}");
            Console.WriteLine($"Date           : {r.Date ?? "Unknown"}");
            Console.WriteLine($"Cashier        : {r.Cashier ?? "Unknown"}");
            Console.WriteLine($"Payment Method : {r.PaymentMethod ?? "Unknown"}");
            
            Console.WriteLine("\nItems:");
            if (r.Items.Count == 0) Console.WriteLine("  (No items detected)");
            foreach (var item in r.Items)
            {
                string qtyStr = item.Qty.HasValue ? $"{item.Qty}x " : "   ";
                Console.WriteLine($"  {qtyStr}{item.Name.PadRight(20)} {item.LinePrice,6:F2}");
            }

            Console.WriteLine("\nTotals:");
            if (r.Subtotal.HasValue) Console.WriteLine($"  Subtotal     : {r.Subtotal,6:F2}");
            if (r.Discount.HasValue) Console.WriteLine($"  Discount     : {r.Discount,6:F2}");
            if (r.Tax.HasValue)      Console.WriteLine($"  Tax          : {r.Tax,6:F2}");
            if (r.Total.HasValue)    Console.WriteLine($"  TOTAL        : {r.Total,6:F2}");
        }
    }

    #region Models

    public class ReceiptExtractionResult
    {
        public Receipt Receipt { get; set; } = new Receipt();
        public List<string> UnclassifiedLines { get; set; } = new List<string>();
    }

    public class Receipt
    {
        public string? Merchant { get; set; }
        public string? Date { get; set; }
        public string? Cashier { get; set; }
        public List<ReceiptItem> Items { get; set; } = new List<ReceiptItem>();
        public decimal? Subtotal { get; set; }
        public decimal? Tax { get; set; }
        public decimal? Total { get; set; }
        public decimal? Discount { get; set; }
        public string? PaymentMethod { get; set; }
    }

    public class ReceiptItem
    {
        public string Name { get; set; } = string.Empty;
        public int? Qty { get; set; }
        public decimal? UnitPrice { get; set; } // Left null for v0.1 heuristic
        public decimal? LinePrice { get; set; }
    }

    #endregion

    #region Extractor

    public class ReceiptExtractor
    {
        // Matches an optional quantity (e.g., "2x " or "12X "), the item name, and a trailing decimal price
        private static readonly Regex ItemRegex = new Regex(@"^(?:(\d+)[xX]\s+)?(.+?)\s+(-?\s*\d+\.\d{2})$", RegexOptions.Compiled);
        
        // Matches trailing decimal prices for totals/taxes
        private static readonly Regex PriceRegex = new Regex(@"(-?\s*\d+\.\d{2})$", RegexOptions.Compiled);

        public ReceiptExtractionResult Extract(List<string> lines)
        {
            var result = new ReceiptExtractionResult();
            var receipt = result.Receipt;
            
            bool merchantFound = false;
            bool insideItemsSection = false;

            for (int i = 0; i < lines.Count; i++)
            {
                string line = lines[i].Trim();
                if (string.IsNullOrWhiteSpace(line)) continue;

                // 1. Skip Dividers
                if (IsDivider(line))
                {
                    if (merchantFound && !insideItemsSection && receipt.Items.Count == 0)
                    {
                        insideItemsSection = true;
                    }
                    continue;
                }

                // 2. Detect Merchant
                if (!merchantFound)
                {
                    receipt.Merchant = line;
                    merchantFound = true;
                    continue;
                }

                string lowerLine = line.ToLowerInvariant();

                // 3. Detect Header Metadata
                if (lowerLine.StartsWith("date:"))
                {
                    receipt.Date = line.Substring(5).Trim();
                    continue;
                }
                if (lowerLine.StartsWith("cashier:"))
                {
                    receipt.Cashier = line.Substring(8).Trim();
                    continue;
                }

                // 4. Detect Payment Footer
                if (lowerLine.StartsWith("paid via"))
                {
                    receipt.PaymentMethod = line.Substring(8).Trim();
                    insideItemsSection = false; 
                    continue;
                }

                // 5. Detect Totals (Safer matching)
                if (lowerLine.Contains("subtotal") || lowerLine.Contains("tax") || lowerLine.Contains("total") || lowerLine.Contains("discount"))
                {
                    insideItemsSection = false;
                    decimal? val = ExtractTrailingDecimal(line);
                    
                    if (val.HasValue)
                    {
                        if (lowerLine.Contains("subtotal")) receipt.Subtotal = val;
                        else if (lowerLine.Contains("discount")) receipt.Discount = val;
                        else if (lowerLine.Contains("tax")) receipt.Tax = val;
                        else if (lowerLine.Contains("total") && !lowerLine.Contains("subtotal")) receipt.Total = val;
                        continue;
                    }
                }

                // 6. Detect Items
                if (insideItemsSection)
                {
                    Match itemMatch = ItemRegex.Match(line);
                    if (itemMatch.Success)
                    {
                        var item = new ReceiptItem();
                        
                        if (itemMatch.Groups[1].Success && int.TryParse(itemMatch.Groups[1].Value, out int qty))
                        {
                            item.Qty = qty;
                        }

                        item.Name = itemMatch.Groups[2].Value.Trim();
                        item.LinePrice = ParseDecimal(itemMatch.Groups[3].Value);

                        receipt.Items.Add(item);
                        continue;
                    }
                }

                // 7. Unclassified 
                result.UnclassifiedLines.Add(line);
            }

            return result;
        }

        private bool IsDivider(string line)
        {
            int dividerChars = line.Count(c => c == '-' || c == '=' || c == '*');
            return dividerChars > (line.Length / 2) && line.Length >= 5;
        }

        private decimal? ExtractTrailingDecimal(string line)
        {
            Match match = PriceRegex.Match(line);
            if (match.Success)
            {
                return ParseDecimal(match.Groups[1].Value);
            }
            return null;
        }

        private decimal? ParseDecimal(string value)
        {
            string cleaned = value.Replace(" ", "");
            if (decimal.TryParse(cleaned, NumberStyles.Any, CultureInfo.InvariantCulture, out decimal result))
            {
                return result;
            }
            return null;
        }
    }

    #endregion
}