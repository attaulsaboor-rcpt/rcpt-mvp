using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;

namespace RCPT_EscPos_Parser
{
    class Program
    {
        static void Main(string[] args)
        {
            // Enable CP437 encoding in .NET
            Encoding.RegisterProvider(CodePagesEncodingProvider.Instance);

            Console.WriteLine("========================================");
            Console.WriteLine("RCPT Bridge - ESC/POS Parser v0.2");
            Console.WriteLine("========================================");

            if (args.Length == 0)
            {
                Console.WriteLine("Usage: RCPT_EscPos_Parser.exe <path_to_bin_or_spl_file>");
                return;
            }

            string filePath = args[0];
            if (!File.Exists(filePath))
            {
                Console.WriteLine($"[ERROR] File not found: {filePath}");
                return;
            }

            try
            {
                byte[] rawData = File.ReadAllBytes(filePath);
                Console.WriteLine($"[LOADED] {filePath} ({rawData.Length} bytes)\n");

                var parser = new EscPosParser();
// We enable trimTrailingEmptyLines by default for cleaner console output
var result = parser.Parse(rawData, trimTrailingEmptyLines: true);

// --- NEW BEHAVIOR: Save CleanedText to file ---
try
{
    string directory = Path.GetDirectoryName(filePath) ?? string.Empty;
    string fileNameWithoutExt = Path.GetFileNameWithoutExtension(filePath);
    string outputFileName = $"{fileNameWithoutExt}_cleaned.txt";
    string outputPath = Path.Combine(directory, outputFileName);

    File.WriteAllText(outputPath, result.CleanedText, Encoding.UTF8);
    Console.WriteLine($"[SAVED] Cleaned receipt text written to: {outputPath}\n");
}
catch (Exception ex)
{
    Console.WriteLine($"[WARNING] Could not save cleaned text to file: {ex.Message}\n");
}

PrintSummary(result);
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[FATAL ERROR] {ex.Message}");
            }
        }

        private static void PrintSummary(ParseResult result)
        {
            Console.WriteLine("--- PARSE SUMMARY ---");
            Console.WriteLine($"Total Bytes Read       : {result.RawByteCount}");
            Console.WriteLine($"Skipped Control Bytes  : {result.SkippedControlByteCount}");
            Console.WriteLine($"Recovered Lines (Raw)  : {result.Lines.Count}");
            
            Console.WriteLine("\n--- RECOGNIZED COMMANDS ---");
            if (result.RecognizedCommands.Count == 0) Console.WriteLine("(None)");
            foreach (var cmd in result.RecognizedCommands)
            {
                Console.WriteLine($"- {cmd}");
            }

            Console.WriteLine("\n--- UNKNOWN COMMANDS (SKIPPED) ---");
            if (result.UnknownCommands.Count == 0) Console.WriteLine("(None)");
            foreach (var cmd in result.UnknownCommands)
            {
                Console.WriteLine($"- {cmd}");
            }

            Console.WriteLine("\n--- EXTRACTED TEXT (PHASE A) ---");
            Console.WriteLine(result.CleanedText);
            Console.WriteLine("--------------------------------");
        }
    }

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
        // Standard ASCII / ESC/POS Control Codes
        private const byte LF = 0x0A;
        private const byte CR = 0x0D;
        private const byte ESC = 0x1B;
        private const byte GS = 0x1D;

        public ParseResult Parse(byte[] data, bool trimTrailingEmptyLines = false)
        {
            var result = new ParseResult { RawByteCount = data.Length };
            var currentLineBytes = new List<byte>();
            Encoding cp437 = Encoding.GetEncoding(437);

            int i = 0;
            while (i < data.Length)
            {
                byte b = data[i];

                // 1. Handle ESC (0x1B) Commands
                if (b == ESC && i + 1 < data.Length)
                {
                    byte next = data[i + 1];

                    if (next == 0x40) // ESC @ (Initialize)
                    {
                        result.RecognizedCommands.Add("ESC @ (Initialize)");
                        result.SkippedControlByteCount += 2;
                        i += 2; continue;
                    }
                    else if (next == 0x61 && i + 2 < data.Length) // ESC a n (Alignment)
                    {
                        result.RecognizedCommands.Add($"ESC a {data[i + 2]:X2} (Alignment)");
                        result.SkippedControlByteCount += 3;
                        i += 3; continue;
                    }
                    else if (next == 0x45 && i + 2 < data.Length) // ESC E n (Emphasized/Bold)
                    {
                        result.RecognizedCommands.Add($"ESC E {data[i + 2]:X2} (Emphasized Mode)");
                        result.SkippedControlByteCount += 3;
                        i += 3; continue;
                    }
                    else if (next == 0x21 && i + 2 < data.Length) // ESC ! n (Print Mode)
                    {
                        result.RecognizedCommands.Add($"ESC ! {data[i + 2]:X2} (Select Print Mode)");
                        result.SkippedControlByteCount += 3;
                        i += 3; continue;
                    }
                    else
                    {
                        // Unknown ESC command. Skip the ESC byte AND the command byte safely.
                        // This prevents the command byte from leaking into the printable text.
                        result.UnknownCommands.Add($"ESC {next:X2}");
                        result.SkippedControlByteCount += 2;
                        i += 2; continue;
                    }
                }

                // 2. Handle GS (0x1D) Commands
                if (b == GS && i + 1 < data.Length)
                {
                    byte next = data[i + 1];

                    if (next == 0x56 && i + 2 < data.Length) // GS V m (Cut)
                    {
                        result.RecognizedCommands.Add($"GS V {data[i + 2]:X2} (Cut Paper)");
                        result.SkippedControlByteCount += 3;
                        i += 3; continue;
                    }
                    else
                    {
                        // Unknown GS command. Skip GS + command byte.
                        result.UnknownCommands.Add($"GS {next:X2}");
                        result.SkippedControlByteCount += 2;
                        i += 2; continue;
                    }
                }

                // 3. Handle Line Breaks
                if (b == LF)
                {
                    string decodedLine = cp437.GetString(currentLineBytes.ToArray());
                    result.Lines.Add(decodedLine);
                    currentLineBytes.Clear();
                    
                    result.SkippedControlByteCount++; // LF is a control byte
                    i++; continue;
                }
                if (b == CR)
                {
                    // Ignore CR, rely on LF for actual line breaks to prevent double-spacing
                    result.SkippedControlByteCount++;
                    i++; continue;
                }

                // 4. Handle Printable Characters vs Garbage Control Codes
                // In CP437, bytes >= 0x20 are printable. Bytes < 0x20 are usually hardware control codes.
                if (b >= 0x20)
                {
                    currentLineBytes.Add(b);
                }
                else
                {
                    // Safely drop unhandled structural/control bytes (like 0x00)
                    result.SkippedControlByteCount++;
                }

                i++;
            }

            // Flush any remaining bytes that didn't end with a LF
            if (currentLineBytes.Count > 0)
            {
                result.Lines.Add(cp437.GetString(currentLineBytes.ToArray()));
            }

            // 5. Post-Processing: Generate CleanedText
            IEnumerable<string> outputLines = result.Lines;
            
            if (trimTrailingEmptyLines)
            {
                int lastNonEmptyIndex = result.Lines.FindLastIndex(l => !string.IsNullOrWhiteSpace(l));
                if (lastNonEmptyIndex >= 0)
                {
                    outputLines = result.Lines.Take(lastNonEmptyIndex + 1);
                }
                else
                {
                    outputLines = Enumerable.Empty<string>();
                }
            }

            result.CleanedText = string.Join(Environment.NewLine, outputLines);
            
            return result;
        }
    }
}