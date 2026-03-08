using System;
using System.Runtime.InteropServices;
using System.Text;

namespace RCPT_Raw_Injector
{
    class Program
    {
        static void Main(string[] args)
        {
            string printerName = "RCPT Test Printer 2";

            // 1. Construct the ESC/POS payload
            // Initialize printer: ESC @ (0x1B 0x40)
            byte[] initCommand = new byte[] { 0x1B, 0x40 };
            
            // Receipt Text
            byte[] textPayload = Encoding.ASCII.GetBytes(
                "RCPT RAW TEST\n" +
                "------------------------\n" +
                "Coffee Beans      6.80\n" +
                "Tea Bags          2.50\n" +
                "------------------------\n" +
                "TOTAL             9.30\n" +
                "\n\n\n\n" // Feed lines
            );
            
            // Cut paper: GS V 0 (0x1D 0x56 0x00)
            byte[] cutCommand = new byte[] { 0x1D, 0x56, 0x00 };

            // Combine into a single byte array
            byte[] fullPayload = new byte[initCommand.Length + textPayload.Length + cutCommand.Length];
            Buffer.BlockCopy(initCommand, 0, fullPayload, 0, initCommand.Length);
            Buffer.BlockCopy(textPayload, 0, fullPayload, initCommand.Length, textPayload.Length);
            Buffer.BlockCopy(cutCommand, 0, fullPayload, initCommand.Length + textPayload.Length, cutCommand.Length);

            Console.WriteLine($"Injecting {fullPayload.Length} bytes of RAW ESC/POS data to '{printerName}'...");

            // 2. Send to Windows Spooler
            bool success = RawPrinterHelper.SendBytesToPrinter(printerName, fullPayload);

            if (success)
            {
                Console.WriteLine("SUCCESS: RAW job submitted to the spooler.");
            }
            else
            {
                int error = Marshal.GetLastWin32Error();
                Console.WriteLine($"FAILED: Could not submit job. Win32 Error Code: {error}");
            }
        }
    }

    public static class RawPrinterHelper
    {
        // Structure required by StartDocPrinter
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

        // CORRECTED: Return type is now int instead of bool
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

        public static bool SendBytesToPrinter(string szPrinterName, byte[] pBytes)
        {
            int dwCount = pBytes.Length;
            IntPtr pUnmanagedBytes = Marshal.AllocCoTaskMem(dwCount);
            Marshal.Copy(pBytes, 0, pUnmanagedBytes, dwCount);
            bool bSuccess = SendBytesToPrinter(szPrinterName, pUnmanagedBytes, dwCount);
            Marshal.FreeCoTaskMem(pUnmanagedBytes);
            return bSuccess;
        }

        private static bool SendBytesToPrinter(string szPrinterName, IntPtr pBytes, int dwCount)
        {
            IntPtr hPrinter = IntPtr.Zero;
            DOCINFOA di = new DOCINFOA();
            bool bSuccess = false;

            di.pDocName = "RCPT RAW Injector Test";
            di.pDataType = "RAW"; // The critical override

            if (OpenPrinter(szPrinterName, out hPrinter, IntPtr.Zero))
            {
                // CORRECTED: Checking if jobId > 0
                int jobId = StartDocPrinter(hPrinter, 1, di);
                if (jobId > 0)
                {
                    if (StartPagePrinter(hPrinter))
                    {
                        bSuccess = WritePrinter(hPrinter, pBytes, dwCount, out int dwWritten);
                        EndPagePrinter(hPrinter);
                    }
                    EndDocPrinter(hPrinter);
                }
                ClosePrinter(hPrinter);
            }
            return bSuccess;
        }
    }
}