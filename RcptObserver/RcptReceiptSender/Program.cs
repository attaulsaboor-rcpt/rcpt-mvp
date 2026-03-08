using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.IO;
using System.Linq;
using System.Printing;
using System.Runtime.InteropServices;
using System.Text;

namespace RCPT_Receipt_Sender
{
    class Program
    {
        private static string TargetPrinterName = "";
        private static readonly string ArtifactsDir = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "OutputArtifacts");

        static void Main(string[] args)
        {
            // Enable extended code pages like CP437 in .NET Core / .NET 8
            Encoding.RegisterProvider(CodePagesEncodingProvider.Instance);

            if (!Directory.Exists(ArtifactsDir))
            {
                Directory.CreateDirectory(ArtifactsDir);
            }

            Console.WriteLine("========================================");
            Console.WriteLine("RCPT Bridge - Local Receipt Sender v0.3");
            Console.WriteLine($"Saving artifacts to: {ArtifactsDir}");
            Console.WriteLine("========================================");

            TargetPrinterName = SelectPrinter();
            if (string.IsNullOrEmpty(TargetPrinterName))
            {
                Console.WriteLine("No printer selected. Exiting...");
                return;
            }

            Console.WriteLine($"\n[READY] Target Printer set to: {TargetPrinterName}");

            while (true)
            {
                Console.WriteLine("\nSelect a receipt payload to send:");
                Console.WriteLine("1. Small Preset (1 item)");
                Console.WriteLine("2. Medium Preset (Standard cafe order)");
                Console.WriteLine("3. Large Preset (Long grocery order with formatting)");
                Console.WriteLine("4. Custom (Type or paste text)");
                Console.WriteLine("5. Exit");
                Console.Write("\nChoice (1-5): ");

                string choice = Console.ReadLine();

                if (choice == "5") break;

                string receiptText = "";

                switch (choice)
                {
                    case "1":
                        receiptText = GetSmallPreset();
                        break;
                    case "2":
                        receiptText = GetMediumPreset();
                        break;
                    case "3":
                        receiptText = GetLargePreset();
                        break;
                    case "4":
                        receiptText = GetCustomReceipt();
                        break;
                    default:
                        Console.WriteLine("Invalid choice. Please try again.");
                        continue;
                }

                if (!string.IsNullOrWhiteSpace(receiptText))
                {
                    ProcessAndSendReceipt(receiptText);
                }
            }
        }

        private static string SelectPrinter()
        {
            Console.WriteLine("\nFetching available printers...");
            List<string> printers = new List<string>();

            try
            {
                using (LocalPrintServer printServer = new LocalPrintServer())
                {
                    foreach (var queue in printServer.GetPrintQueues())
                    {
                        printers.Add(queue.Name);
                    }
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[ERROR] Could not enumerate printers: {ex.Message}");
                return null;
            }

            if (printers.Count == 0)
            {
                Console.WriteLine("[ERROR] No printers found on this system.");
                return null;
            }

            for (int i = 0; i < printers.Count; i++)
            {
                Console.WriteLine($"{i + 1}. {printers[i]}");
            }

            while (true)
            {
                Console.Write($"\nSelect printer (1-{printers.Count}): ");
                if (int.TryParse(Console.ReadLine(), out int choice) && choice >= 1 && choice <= printers.Count)
                {
                    return printers[choice - 1];
                }
                Console.WriteLine("Invalid selection.");
            }
        }

        private static void ProcessAndSendReceipt(string rawText)
        {
            // 1. Wrap in basic ESC/POS commands
            byte[] initCommand = { 0x1B, 0x40 }; // ESC @
            
            // Convert using CP437 for accurate POS character mapping
            Encoding cp437 = Encoding.GetEncoding(437);
            byte[] textBytes = cp437.GetBytes(rawText + "\n\n\n\n"); 
            
            byte[] cutCommand = { 0x1D, 0x56, 0x00 }; // GS V 0

            byte[] fullPayload = new byte[initCommand.Length + textBytes.Length + cutCommand.Length];
            Buffer.BlockCopy(initCommand, 0, fullPayload, 0, initCommand.Length);
            Buffer.BlockCopy(textBytes, 0, fullPayload, initCommand.Length, textBytes.Length);
            Buffer.BlockCopy(cutCommand, 0, fullPayload, initCommand.Length + textBytes.Length, cutCommand.Length);

            // 2. Save Artifacts with millisecond precision
            string timestamp = DateTime.Now.ToString("yyyyMMdd_HHmmss_fff");
            string binPath = Path.Combine(ArtifactsDir, $"receipt_{timestamp}.bin");
            string txtPath = Path.Combine(ArtifactsDir, $"receipt_{timestamp}.txt");

            File.WriteAllBytes(binPath, fullPayload);
            File.WriteAllText(txtPath, rawText, cp437);
            
            Console.WriteLine($"\n[ARTIFACTS SAVED] -> {Path.GetFileName(binPath)}");

            // 3. Send to Spooler
            Console.WriteLine($"[SPOOLING] Sending {fullPayload.Length} bytes to '{TargetPrinterName}'...");
            var result = RawPrinterHelper.SendBytesToPrinter(TargetPrinterName, fullPayload);

            if (result.Success)
            {
                Console.WriteLine("[SUCCESS] RAW job completely written to Windows Spooler.");
            }
            else
            {
                Console.WriteLine($"[FAILED] {result.ErrorMessage}");
            }
        }

        private static string GetSmallPreset()
        {
            return "RCPT COFFEE SHOP\n" +
                   "------------------------\n" +
                   "1x Black Coffee     2.50\n" +
                   "------------------------\n" +
                   "TOTAL               2.50\n";
        }

        private static string GetMediumPreset()
        {
            return "RCPT CAFE & BAKERY\n" +
                   "123 Campus Drive\n" +
                   "Receipt: #45992\n" +
                   "------------------------\n" +
                   "2x Latte            9.00\n" +
                   "1x Croissant        3.50\n" +
                   "1x Muffin           2.75\n" +
                   "------------------------\n" +
                   "Subtotal           15.25\n" +
                   "Tax (8%)            1.22\n" +
                   "TOTAL              16.47\n" +
                   "------------------------\n" +
                   "Paid via Credit Card\n";
        }

        private static string GetLargePreset()
        {
            StringBuilder sb = new StringBuilder();
            sb.AppendLine("RCPT GROCERY MART");
            sb.AppendLine("Store #004 - Main Campus");
            sb.AppendLine("Date: " + DateTime.Now.ToString("yyyy-MM-dd HH:mm"));
            sb.AppendLine("Cashier: Register 3");
            sb.AppendLine("--------------------------------");
            
            for (int i = 1; i <= 15; i++)
            {
                sb.AppendLine($"Item {i,-20} 1.99");
            }
            
            sb.AppendLine("--------------------------------");
            sb.AppendLine("Subtotal                   29.85");
            sb.AppendLine("Student Discount          - 2.98");
            sb.AppendLine("Tax                         2.15");
            sb.AppendLine("TOTAL                      29.02");
            sb.AppendLine("--------------------------------");
            sb.AppendLine("Thank you for shopping with us!");
            sb.AppendLine("Please come again.");
            return sb.ToString();
        }

        private static string GetCustomReceipt()
        {
            Console.WriteLine("\nType or paste your receipt text.");
            Console.WriteLine("Type 'END' on a new line and press Enter to finish:\n");
            
            List<string> lines = new List<string>();
            while (true)
            {
                string line = Console.ReadLine();
                if (line != null && line.Trim().ToUpper() == "END")
                {
                    break;
                }
                lines.Add(line);
            }
            return string.Join("\n", lines);
        }
    }

    public static class RawPrinterHelper
    {
        [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Ansi)]
        public class DOCINFOA
        {
            [MarshalAs(UnmanagedType.LPStr)] public string pDocName;
            [MarshalAs(UnmanagedType.LPStr)] public string pOutputFile;
            [MarshalAs(UnmanagedType.LPStr)] public string pDataType;
        }

        [DllImport("winspool.Drv", EntryPoint = "OpenPrinterA", SetLastError = true, CharSet = CharSet.Ansi, ExactSpelling = true, CallingConvention = CallingConvention.StdCall)]
        public static extern bool OpenPrinter([MarshalAs(UnmanagedType.LPStr)] string szPrinter, out IntPtr hPrinter, IntPtr pd);

        [DllImport("winspool.Drv", EntryPoint = "ClosePrinter", SetLastError = true, ExactSpelling = true, CallingConvention = CallingConvention.StdCall)]
        public static extern bool ClosePrinter(IntPtr hPrinter);

        [DllImport("winspool.Drv", EntryPoint = "StartDocPrinterA", SetLastError = true, CharSet = CharSet.Ansi, ExactSpelling = true, CallingConvention = CallingConvention.StdCall)]
        public static extern int StartDocPrinter(IntPtr hPrinter, int level, [In, MarshalAs(UnmanagedType.LPStruct)] DOCINFOA di);

        [DllImport("winspool.Drv", EntryPoint = "EndDocPrinter", SetLastError = true, ExactSpelling = true, CallingConvention = CallingConvention.StdCall)]
        public static extern bool EndDocPrinter(IntPtr hPrinter);

        [DllImport("winspool.Drv", EntryPoint = "StartPagePrinter", SetLastError = true, ExactSpelling = true, CallingConvention = CallingConvention.StdCall)]
        public static extern bool StartPagePrinter(IntPtr hPrinter);

        [DllImport("winspool.Drv", EntryPoint = "EndPagePrinter", SetLastError = true, ExactSpelling = true, CallingConvention = CallingConvention.StdCall)]
        public static extern bool EndPagePrinter(IntPtr hPrinter);

        [DllImport("winspool.Drv", EntryPoint = "WritePrinter", SetLastError = true, ExactSpelling = true, CallingConvention = CallingConvention.StdCall)]
        public static extern bool WritePrinter(IntPtr hPrinter, IntPtr pBytes, int dwCount, out int dwWritten);

        public static (bool Success, string ErrorMessage) SendBytesToPrinter(string szPrinterName, byte[] pBytes)
        {
            int dwCount = pBytes.Length;
            IntPtr pUnmanagedBytes = Marshal.AllocCoTaskMem(dwCount);
            Marshal.Copy(pBytes, 0, pUnmanagedBytes, dwCount);
            
            var result = SendBytesToPrinterInternal(szPrinterName, pUnmanagedBytes, dwCount);
            
            Marshal.FreeCoTaskMem(pUnmanagedBytes);
            return result;
        }

        private static (bool Success, string ErrorMessage) SendBytesToPrinterInternal(string szPrinterName, IntPtr pBytes, int dwCount)
        {
            IntPtr hPrinter = IntPtr.Zero;
            DOCINFOA di = new DOCINFOA();

            di.pDocName = "RCPT Local Sender Form";
            di.pDataType = "RAW";

            bool printerOpen = false;
            bool docStarted = false;
            bool pageStarted = false;

            try
            {
                if (!OpenPrinter(szPrinterName, out hPrinter, IntPtr.Zero))
                    return (false, GetWin32ErrorMessage("OpenPrinter"));
                
                printerOpen = true;

                int jobId = StartDocPrinter(hPrinter, 1, di);
                if (jobId <= 0)
                    return (false, GetWin32ErrorMessage("StartDocPrinter"));

                docStarted = true;

                if (!StartPagePrinter(hPrinter))
                    return (false, GetWin32ErrorMessage("StartPagePrinter"));

                pageStarted = true;

                bool bSuccess = WritePrinter(hPrinter, pBytes, dwCount, out int dwWritten);
                
                if (!bSuccess)
                    return (false, GetWin32ErrorMessage("WritePrinter"));

                if (dwWritten != dwCount)
                    return (false, $"WritePrinter partial write: Attempted {dwCount} bytes, but only wrote {dwWritten} bytes.");

                return (true, string.Empty);
            }
            finally
            {
                // Safely tear down the Win32 state machine in reverse order
                if (pageStarted)
                    EndPagePrinter(hPrinter);
                
                if (docStarted)
                    EndDocPrinter(hPrinter);
                
                if (printerOpen && hPrinter != IntPtr.Zero)
                    ClosePrinter(hPrinter);
            }
        }

        private static string GetWin32ErrorMessage(string functionName)
        {
            int error = Marshal.GetLastWin32Error();
            string message = new Win32Exception(error).Message;
            return $"{functionName} failed. Win32 Error {error}: {message}";
        }
    }
}