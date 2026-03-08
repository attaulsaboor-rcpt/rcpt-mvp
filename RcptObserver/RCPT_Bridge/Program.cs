using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Net.Http;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Text.RegularExpressions;
using System.Threading;
using System.Threading.Tasks;

namespace RCPT_Bridge
{
    class Program
    {
        private const string SpoolDirectory = @"C:\Windows\System32\spool\PRINTERS\";
        private static readonly ConcurrentQueue<string> _jobQueue = new ConcurrentQueue<string>();
        private static readonly ConcurrentDictionary<string, FileState> _fileStates = new ConcurrentDictionary<string, FileState>(StringComparer.OrdinalIgnoreCase);
        
        // --- Configuration ---
        private const bool DebugMode = true; 
        private static readonly string ArtifactsDir = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "DebugArtifacts");

        // --- API Configuration ---
        public static readonly string ApiBaseUrl = string.IsNullOrWhiteSpace(Environment.GetEnvironmentVariable("RCPT_API_BASE_URL")) 
            ? "http://localhost:8000" 
            : Environment.GetEnvironmentVariable("RCPT_API_BASE_URL").TrimEnd('/');
            
        public const string IngestEndpoint = "/api/receipts/ingest";
        public const string TerminalId = "terminal-001";
        public const int ApiTimeoutSeconds = 10;

        // Static HttpClient per Microsoft best practices to prevent socket exhaustion
        private static readonly HttpClient _httpClient = new HttpClient();

        static async Task Main(string[] args)
        {
            Encoding.RegisterProvider(CodePagesEncodingProvider.Instance);
            
            _httpClient.Timeout = TimeSpan.FromSeconds(ApiTimeoutSeconds);

            Console.WriteLine("==================================================");
            Console.WriteLine("RCPT Bridge v0.2.3 - Background Daemon (Idempotent)");
            Console.WriteLine($"Watching: {SpoolDirectory}");
            Console.WriteLine($"API Target: {ApiBaseUrl}{IngestEndpoint}");
            Console.WriteLine($"Terminal ID: {TerminalId}");
            Console.WriteLine($"Debug Mode: {(DebugMode ? "ON (Saving Artifacts)" : "OFF (In-Memory Only)")}");
            Console.WriteLine("==================================================\n");

            if (DebugMode && !Directory.Exists(ArtifactsDir))
            {
                Directory.CreateDirectory(ArtifactsDir);
            }

            if (!Directory.Exists(SpoolDirectory))
            {
                Console.WriteLine($"[FATAL ERROR] Spool directory does not exist or requires Admin privileges: {SpoolDirectory}");
                return;
            }

            using var cts = new CancellationTokenSource();
            
            Console.CancelKeyPress += (sender, e) =>
            {
                e.Cancel = true;
                Console.WriteLine("\n[SYSTEM] Ctrl+C detected. Shutting down gracefully...");
                cts.Cancel();
            };

            Task consumerTask = Task.Run(() => ConsumerLoopAsync(cts.Token), cts.Token);

            using var watcher = new FileSystemWatcher(SpoolDirectory, "*.SPL")
            {
                NotifyFilter = NotifyFilters.FileName | NotifyFilters.Size | NotifyFilters.LastWrite,
                InternalBufferSize = 65536 
            };

            watcher.Created += OnSpoolFileEvent;
            watcher.Changed += OnSpoolFileEvent;
            watcher.Error += OnWatcherError;
            watcher.EnableRaisingEvents = true;

            Console.WriteLine("[SYSTEM] Spool Watcher active. Waiting for receipts...");

            try
            {
                await Task.Delay(-1, cts.Token);
            }
            catch (TaskCanceledException) { /* Expected on shutdown */ }
            
            watcher.EnableRaisingEvents = false;
            await consumerTask; 
            
            Console.WriteLine("[SYSTEM] Shutdown complete.");
        }

        private static void OnSpoolFileEvent(object sender, FileSystemEventArgs e)
        {
            var state = _fileStates.GetOrAdd(e.FullPath, _ => new FileState());
            state.LastSeen = DateTime.Now;

            if ((DateTime.Now - state.LastEnqueued).TotalMilliseconds < 200) return;

            state.LastEnqueued = DateTime.Now;
            _jobQueue.Enqueue(e.FullPath);
        }

        private static void OnWatcherError(object sender, ErrorEventArgs e)
        {
            Console.WriteLine($"[WATCHER ERROR] {e.GetException().Message}");
        }

        private static async Task ConsumerLoopAsync(CancellationToken token)
        {
            var processor = new BridgeProcessor(_httpClient);
            DateTime lastCleanup = DateTime.Now;

            while (!token.IsCancellationRequested)
            {
                if ((DateTime.Now - lastCleanup).TotalMinutes > 5)
                {
                    CleanupCache();
                    lastCleanup = DateTime.Now;
                }

                if (_jobQueue.TryDequeue(out string filePath))
                {
                    try
                    {
                        await processor.ProcessSpoolJobAsync(filePath, DebugMode, ArtifactsDir, _fileStates, token);
                    }
                    catch (Exception ex)
                    {
                        Console.WriteLine($"[WORKER ERROR] Unhandled exception processing {Path.GetFileName(filePath)}: {ex.Message}");
                    }
                }
                else
                {
                    try
                    {
                        await Task.Delay(100, token);
                    }
                    catch (TaskCanceledException)
                    {
                        break;
                    }
                }
            }
        }

        private static void CleanupCache()
        {
            var now = DateTime.Now;
            foreach (var kvp in _fileStates)
            {
                if ((now - kvp.Value.LastSeen).TotalMinutes > 10)
                {
                    _fileStates.TryRemove(kvp.Key, out _);
                }
            }
        }
    }

    public class FileState
    {
        public DateTime LastEnqueued { get; set; } = DateTime.MinValue;
        public DateTime LastSeen { get; set; } = DateTime.Now;
        public long LastProcessedSize { get; set; } = -1;
    }

    #region Pipeline Orchestrator

    public class BridgeProcessor
    {
        private readonly EscPosParser _parser = new EscPosParser();
        private readonly ReceiptExtractor _extractor = new ReceiptExtractor();
        private readonly HttpClient _httpClient;

        public BridgeProcessor(HttpClient httpClient)
        {
            _httpClient = httpClient;
        }

        public async Task ProcessSpoolJobAsync(string filePath, bool debugMode, string artifactsDir, ConcurrentDictionary<string, FileState> fileStates, CancellationToken token)
        {
            // STAGE 1: Read Bytes via Stability Loop
            byte[] rawBytes = await ReadSpoolBytesStableAsync(filePath, token);
            if (rawBytes == null || rawBytes.Length == 0) return;

            var state = fileStates.GetOrAdd(filePath, _ => new FileState());
            
            if (state.LastProcessedSize == rawBytes.Length)
            {
                return; // Duplicate size
            }

            string fileName = Path.GetFileName(filePath);
            Console.WriteLine($"\n--- PROCESSING JOB: {fileName} ---");
            Console.WriteLine($"[STAGE 1] Read Success: {rawBytes.Length} bytes.");

            state.LastProcessedSize = rawBytes.Length;

            // STAGE 1.5: Generate Idempotency Key (SHA-256 of raw bytes)
            string idempotencyKey = ComputeSha256Hash(rawBytes);

            // STAGE 2: Parse to Clean Text
            ParseResult parseResult = _parser.Parse(rawBytes, trimTrailingEmptyLines: true);
            
            if (string.IsNullOrWhiteSpace(parseResult.CleanedText))
            {
                Console.WriteLine($"[STAGE 2] Parse returned empty/whitespace-only text. Skipping extraction.");
                return;
            }
            Console.WriteLine($"[STAGE 2] Parse Success: {parseResult.Lines.Count} text lines recovered.");

            // STAGE 3: Extract Structured Receipt
            ReceiptExtractionResult extractResult = _extractor.Extract(parseResult.Lines);
            Receipt receipt = extractResult.Receipt;
            Console.WriteLine($"[STAGE 3] Extract Success: Identified merchant '{receipt.Merchant ?? "Unknown"}' and {receipt.Items.Count} items.");

            // STAGE 4: JSON Serialization
            var payload = new ReceiptPayload
            {
                IdempotencyKey = idempotencyKey,
                TerminalId = Program.TerminalId,
                SourceFile = fileName,
                CapturedAtUtc = DateTime.UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ"),
                Receipt = receipt
            };

            string jsonPayload = JsonSerializer.Serialize(payload, new JsonSerializerOptions { WriteIndented = true });
            Console.WriteLine($"[STAGE 4] JSON serialization success. (Key: {idempotencyKey.Substring(0,8)}...)");

            if (debugMode)
            {
                SaveArtifacts(fileName, rawBytes, parseResult.CleanedText, jsonPayload, artifactsDir);
            }

            // STAGE 5: API POST with Retries
            await PostReceiptToBackendAsync(jsonPayload, idempotencyKey, fileName, token);
            
            Console.WriteLine("-----------------------------------");
        }

        private static string ComputeSha256Hash(byte[] rawData)
        {
            using (SHA256 sha256Hash = SHA256.Create())
            {
                byte[] bytes = sha256Hash.ComputeHash(rawData);
                StringBuilder builder = new StringBuilder();
                for (int i = 0; i < bytes.Length; i++)
                {
                    builder.Append(bytes[i].ToString("x2"));
                }
                return builder.ToString();
            }
        }

        private async Task PostReceiptToBackendAsync(string jsonPayload, string idempotencyKey, string fileName, CancellationToken token)
        {
            int maxRetries = 3;
            int delayMs = 1500;
            string targetUrl = $"{Program.ApiBaseUrl}{Program.IngestEndpoint}";

            Console.WriteLine($"[STAGE 5] POSTing receipt to {targetUrl}...");

            for (int attempt = 1; attempt <= maxRetries; attempt++)
            {
                if (token.IsCancellationRequested) return;

                try
                {
                    using var request = new HttpRequestMessage(HttpMethod.Post, targetUrl);
                    request.Headers.Add("X-Idempotency-Key", idempotencyKey);
                    request.Content = new StringContent(jsonPayload, Encoding.UTF8, "application/json");
                    
                    HttpResponseMessage response = await _httpClient.SendAsync(request, token);

                    if (response.IsSuccessStatusCode)
                    {
                        Console.WriteLine($"[STAGE 5] API POST success (Attempt {attempt}/{maxRetries}): HTTP {(int)response.StatusCode} {response.ReasonPhrase}");
                        return; // Done
                    }
                    else
                    {
                        string errorBody = await response.Content.ReadAsStringAsync(token);
                        Console.WriteLine($"[STAGE 5 WARNING] API POST failed (Attempt {attempt}/{maxRetries}): HTTP {(int)response.StatusCode} {response.ReasonPhrase}");
                        if (!string.IsNullOrWhiteSpace(errorBody))
                        {
                            Console.WriteLine($"          Body: {errorBody}");
                        }
                    }
                }
                catch (TaskCanceledException ex) when (!token.IsCancellationRequested)
                {
                    Console.WriteLine($"[STAGE 5 WARNING] API POST timeout (Attempt {attempt}/{maxRetries}): The request exceeded {Program.ApiTimeoutSeconds} seconds. {ex.Message}");
                }
                catch (TaskCanceledException)
                {
                    return; // Clean shutdown requested during the API call
                }
                catch (Exception ex)
                {
                    Console.WriteLine($"[STAGE 5 WARNING] API POST error (Attempt {attempt}/{maxRetries}): {ex.Message}");
                }

                if (attempt < maxRetries)
                {
                    Console.WriteLine($"          Waiting {delayMs}ms before retry...");
                    try
                    {
                        await Task.Delay(delayMs, token);
                    }
                    catch (TaskCanceledException)
                    {
                        return; // Exit retry loop on shutdown
                    }
                }
            }

            Console.WriteLine($"[STAGE 5 ERROR] API POST failed completely for {fileName} after {maxRetries} attempts.");
        }

        private async Task<byte[]> ReadSpoolBytesStableAsync(string filePath, CancellationToken token)
        {
            int maxRetries = 10;
            int delayMs = 200;
            long lastSize = -1;

            for (int i = 0; i < maxRetries; i++)
            {
                if (token.IsCancellationRequested) return null;

                try
                {
                    using (var fs = new FileStream(filePath, FileMode.Open, FileAccess.Read, FileShare.ReadWrite))
                    {
                        long currentSize = fs.Length;
                        
                        if (currentSize > 0 && currentSize == lastSize)
                        {
                            using (var ms = new MemoryStream())
                            {
                                await fs.CopyToAsync(ms, token);
                                return ms.ToArray();
                            }
                        }
                        lastSize = currentSize;
                    }
                }
                catch (FileNotFoundException) { return null; }
                catch (IOException) { }
                catch (Exception ex) { Console.WriteLine($"[STAGE 1 ERROR] {ex.Message}"); return null; }

                try
                {
                    await Task.Delay(delayMs, token);
                }
                catch (TaskCanceledException)
                {
                    return null; // Exit stability loop on shutdown
                }
            }
            
            Console.WriteLine($"[STAGE 1 WARNING] File {Path.GetFileName(filePath)} did not stabilize after {maxRetries} retries.");
            return null;
        }

        private void SaveArtifacts(string originalName, byte[] rawBytes, string cleanedText, string jsonPayload, string artifactsDir)
        {
            try
            {
                string baseName = Path.GetFileNameWithoutExtension(originalName);
                string ts = DateTime.Now.ToString("HHmmss_fff");
                
                File.WriteAllBytes(Path.Combine(artifactsDir, $"{baseName}_{ts}.bin"), rawBytes);
                File.WriteAllText(Path.Combine(artifactsDir, $"{baseName}_{ts}_cleaned.txt"), cleanedText, Encoding.UTF8);
                File.WriteAllText(Path.Combine(artifactsDir, $"{baseName}_{ts}_payload.json"), jsonPayload, Encoding.UTF8);
                Console.WriteLine($"[DEBUG] Saved .bin, _cleaned.txt, and _payload.json artifacts locally.");
            }
            catch { /* Ignore artifact saving errors */ }
        }
    }

    #endregion

    #region DTOs & Models

    public class ReceiptPayload
    {
        [JsonPropertyName("idempotency_key")]
        public string IdempotencyKey { get; set; } = string.Empty;

        [JsonPropertyName("terminal_id")]
        public string TerminalId { get; set; } = string.Empty;

        [JsonPropertyName("source_file")]
        public string SourceFile { get; set; } = string.Empty;

        [JsonPropertyName("captured_at_utc")]
        public string CapturedAtUtc { get; set; } = string.Empty;

        [JsonPropertyName("receipt")]
        public Receipt Receipt { get; set; } = new Receipt();
    }

    public class ReceiptExtractionResult
    {
        public Receipt Receipt { get; set; } = new Receipt();
        public List<string> UnclassifiedLines { get; set; } = new List<string>();
    }

    public class Receipt
    {
        [JsonPropertyName("merchant")]
        public string? Merchant { get; set; }
        
        [JsonPropertyName("date")]
        public string? Date { get; set; }
        
        [JsonPropertyName("cashier")]
        public string? Cashier { get; set; }
        
        [JsonPropertyName("paymentMethod")]
        public string? PaymentMethod { get; set; }
        
        [JsonPropertyName("subtotal")]
        public decimal? Subtotal { get; set; }
        
        [JsonPropertyName("discount")]
        public decimal? Discount { get; set; }
        
        [JsonPropertyName("tax")]
        public decimal? Tax { get; set; }
        
        [JsonPropertyName("total")]
        public decimal? Total { get; set; }
        
        [JsonPropertyName("items")]
        public List<ReceiptItem> Items { get; set; } = new List<ReceiptItem>();
    }

    public class ReceiptItem
    {
        [JsonPropertyName("name")]
        public string Name { get; set; } = string.Empty;
        
        [JsonPropertyName("qty")]
        public int? Qty { get; set; }
        
        [JsonPropertyName("unitPrice")]
        public decimal? UnitPrice { get; set; } 
        
        [JsonPropertyName("linePrice")]
        public decimal? LinePrice { get; set; }
    }

    #endregion

    #region Module: Parser

    public class ParseResult
    {
        public int RawByteCount { get; set; }
        public string CleanedText { get; set; } = string.Empty;
        public List<string> Lines { get; set; } = new List<string>();
        public int SkippedControlByteCount { get; set; }
        public List<string> RecognizedCommands { get; set; } = new List<string>();
        public List<string> UnknownCommands { get; set; } = new List<string>();
    }

    public class EscPosParser
    {
        private const byte LF = 0x0A, CR = 0x0D, ESC = 0x1B, GS = 0x1D;

        public ParseResult Parse(byte[] data, bool trimTrailingEmptyLines = false)
        {
            var result = new ParseResult { RawByteCount = data.Length };
            var currentLineBytes = new List<byte>();
            Encoding cp437 = Encoding.GetEncoding(437);

            int i = 0;
            while (i < data.Length)
            {
                byte b = data[i];

                if (b == ESC && i + 1 < data.Length)
                {
                    byte next = data[i + 1];
                    if (next == 0x40) { i += 2; continue; } 
                    if (next == 0x61 && i + 2 < data.Length) { i += 3; continue; } 
                    if (next == 0x45 && i + 2 < data.Length) { i += 3; continue; } 
                    if (next == 0x21 && i + 2 < data.Length) { i += 3; continue; } 
                    i += 2; continue; 
                }

                if (b == GS && i + 1 < data.Length)
                {
                    byte next = data[i + 1];
                    if (next == 0x56 && i + 2 < data.Length) { i += 3; continue; } 
                    i += 2; continue; 
                }

                if (b == LF)
                {
                    result.Lines.Add(cp437.GetString(currentLineBytes.ToArray()));
                    currentLineBytes.Clear();
                    i++; continue;
                }
                
                if (b == CR) { i++; continue; }

                if (b >= 0x20) currentLineBytes.Add(b);
                i++;
            }

            if (currentLineBytes.Count > 0)
                result.Lines.Add(cp437.GetString(currentLineBytes.ToArray()));

            IEnumerable<string> outputLines = result.Lines;
            if (trimTrailingEmptyLines)
            {
                int lastNonEmpty = result.Lines.FindLastIndex(l => !string.IsNullOrWhiteSpace(l));
                outputLines = lastNonEmpty >= 0 ? result.Lines.Take(lastNonEmpty + 1) : Enumerable.Empty<string>();
            }

            result.CleanedText = string.Join(Environment.NewLine, outputLines);
            return result;
        }
    }

    #endregion

    #region Module: Extractor

    public class ReceiptExtractor
    {
        private static readonly Regex ItemRegex = new Regex(@"^(?:(\d+)[xX]\s+)?(.+?)\s+(-?\s*\d+\.\d{2})$", RegexOptions.Compiled);
        private static readonly Regex PriceRegex = new Regex(@"(-?\s*\d+\.\d{2})$", RegexOptions.Compiled);

        public ReceiptExtractionResult Extract(List<string> lines)
        {
            var result = new ReceiptExtractionResult();
            var receipt = result.Receipt;
            
            bool merchantFound = false, insideItemsSection = false;

            foreach (var rawLine in lines)
            {
                string line = rawLine.Trim();
                if (string.IsNullOrWhiteSpace(line)) continue;

                if (IsDivider(line))
                {
                    if (merchantFound && !insideItemsSection && receipt.Items.Count == 0)
                        insideItemsSection = true;
                    continue;
                }

                if (!merchantFound)
                {
                    receipt.Merchant = line;
                    merchantFound = true;
                    continue;
                }

                string lowerLine = line.ToLowerInvariant();

                if (lowerLine.StartsWith("date:")) { receipt.Date = line.Substring(5).Trim(); continue; }
                if (lowerLine.StartsWith("cashier:")) { receipt.Cashier = line.Substring(8).Trim(); continue; }
                if (lowerLine.StartsWith("paid via")) { receipt.PaymentMethod = line.Substring(8).Trim(); insideItemsSection = false; continue; }

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

                if (insideItemsSection)
                {
                    Match itemMatch = ItemRegex.Match(line);
                    if (itemMatch.Success)
                    {
                        var item = new ReceiptItem { Name = itemMatch.Groups[2].Value.Trim(), LinePrice = ParseDecimal(itemMatch.Groups[3].Value) };
                        if (itemMatch.Groups[1].Success && int.TryParse(itemMatch.Groups[1].Value, out int qty)) item.Qty = qty;
                        receipt.Items.Add(item);
                        continue;
                    }
                }

                result.UnclassifiedLines.Add(line);
            }
            return result;
        }

        private bool IsDivider(string line) => line.Count(c => c == '-' || c == '=' || c == '*') > (line.Length / 2) && line.Length >= 5;
        private decimal? ExtractTrailingDecimal(string line) => PriceRegex.Match(line).Success ? ParseDecimal(PriceRegex.Match(line).Groups[1].Value) : null;
        private decimal? ParseDecimal(string value) => decimal.TryParse(value.Replace(" ", ""), NumberStyles.Any, CultureInfo.InvariantCulture, out decimal res) ? res : null;
    }

    #endregion
}