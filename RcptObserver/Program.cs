using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Printing;
using System.Text;
using System.Threading;

namespace RCPT_Bridge_Experiment
{
    class Program
    {
        private const string TargetPrinterName = "RCPT Test Printer 2";
        private const int PollingIntervalMs = 200;
        private const string SpoolDirectory = @"C:\Windows\System32\spool\PRINTERS";
        private const int PreviewByteCount = 256;
        
        private static readonly string BaseDir = AppDomain.CurrentDomain.BaseDirectory;
        private static readonly string LogFilePath = Path.Combine(BaseDir, "SpoolCorrelationExperiment.csv");
        private static readonly string InterceptDirectory = Path.Combine(BaseDir, "InterceptedSpools");
        
        private static readonly object _logLock = new object();
        private static Dictionary<int, PrintJobStatus> _activeJobs = new Dictionary<int, PrintJobStatus>();

        static void Main(string[] args)
        {
            using CancellationTokenSource cts = new CancellationTokenSource();
            
            Console.CancelKeyPress += (sender, e) =>
            {
                e.Cancel = true;
                LogConsole("SYSTEM", "SHUTDOWN", "CTRL+C detected. Exiting gracefully...");
                cts.Cancel();
            };

            InitializeEnvironment();

            using FileSystemWatcher watcher = new FileSystemWatcher(SpoolDirectory);
            SetupFileSystemWatcher(watcher);

            try
            {
                using LocalPrintServer printServer = new LocalPrintServer();
                PrintQueue queue = printServer.GetPrintQueues()
                    .FirstOrDefault(q => q.Name.Equals(TargetPrinterName, StringComparison.OrdinalIgnoreCase));

                if (queue == null)
                {
                    LogConsole("SYSTEM", "ERROR", $"Target printer '{TargetPrinterName}' not found.");
                    return;
                }

                LogConsole("SYSTEM", "STARTUP", $"Monitoring Queue: {queue.Name} | Spool Dir: {SpoolDirectory}");
                watcher.EnableRaisingEvents = true;

                while (!cts.Token.IsCancellationRequested)
                {
                    PollPrintQueue(queue);
                    
                    if (!cts.Token.IsCancellationRequested)
                    {
                        Thread.Sleep(PollingIntervalMs);
                    }
                }
            }
            catch (Exception ex)
            {
                LogConsole("SYSTEM", "FATAL", ex.Message);
            }
        }

        private static void InitializeEnvironment()
        {
            if (!Directory.Exists(InterceptDirectory))
            {
                Directory.CreateDirectory(InterceptDirectory);
            }

            lock (_logLock)
            {
                if (!File.Exists(LogFilePath))
                {
                    File.WriteAllText(LogFilePath, "Timestamp,Layer,Event,Identifier,Size(Bytes),Details\n");
                }
            }
        }

        private static void PollPrintQueue(PrintQueue queue)
        {
            try
            {
                queue.Refresh();
                var currentJobs = queue.GetPrintJobInfoCollection();
                var currentJobIds = new HashSet<int>();

                foreach (var job in currentJobs)
                {
                    currentJobIds.Add(job.JobIdentifier);
                    string jobIdStr = $"Job {job.JobIdentifier:D5}";

                    if (!_activeJobs.ContainsKey(job.JobIdentifier))
                    {
                        _activeJobs[job.JobIdentifier] = job.JobStatus;
                        LogCsv("API", "JobCreated", jobIdStr, job.JobSize, job.JobStatus.ToString());
                    }
                    else if (_activeJobs[job.JobIdentifier] != job.JobStatus)
                    {
                        _activeJobs[job.JobIdentifier] = job.JobStatus;
                        LogCsv("API", "StatusChanged", jobIdStr, job.JobSize, job.JobStatus.ToString());
                    }
                }

                var removedJobIds = _activeJobs.Keys.Where(id => !currentJobIds.Contains(id)).ToList();
                foreach (var id in removedJobIds)
                {
                    LogCsv("API", "JobRemoved", $"Job {id:D5}", 0, "Deleted from queue");
                    _activeJobs.Remove(id);
                }
            }
            catch (Exception ex)
            {
                LogCsv("API", "Error", "QueueRefresh", 0, ex.Message);
            }
        }

        private static void SetupFileSystemWatcher(FileSystemWatcher watcher)
        {
            watcher.NotifyFilter = NotifyFilters.FileName | NotifyFilters.Size | NotifyFilters.LastWrite;
            watcher.Filter = "*.SPL"; 

            watcher.Created += (s, e) => HandleFileEvent("FileCreated", e.FullPath, e.Name);
            watcher.Changed += (s, e) => HandleFileEvent("FileChanged", e.FullPath, e.Name);
            watcher.Deleted += (s, e) => LogCsv("FS", "FileDeleted", e.Name, 0, "Observed in spool dir");
            watcher.Error += (s, e) => LogCsv("FS", "WatcherError", "N/A", 0, e.GetException().Message);
        }

        private static void HandleFileEvent(string eventType, string fullPath, string fileName)
        {
            long fileSize = GetSafeFileSize(fullPath);
            LogCsv("FS", eventType, fileName, fileSize, "Triggered safe read attempt");
            AttemptSafeFileRead(fullPath, fileName);
        }

        private static void AttemptSafeFileRead(string sourcePath, string fileName)
        {
            string destPath = Path.Combine(InterceptDirectory, $"{DateTime.Now:HHmmss_fff}_{fileName}");
            
            try
            {
                byte[] capturedBytes;

                using (FileStream fs = new FileStream(sourcePath, FileMode.Open, FileAccess.Read, FileShare.ReadWrite))
                {
                    using (MemoryStream ms = new MemoryStream())
                    {
                        fs.CopyTo(ms);
                        capturedBytes = ms.ToArray();
                    }
                }

                if (capturedBytes.Length > 0)
                {
                    File.WriteAllBytes(destPath, capturedBytes);
                    LogCsv("FS", "ReadSuccess", fileName, capturedBytes.Length, $"Saved to {Path.GetFileName(destPath)}");
                    PrintPreview(fileName, capturedBytes);
                }
            }
            catch (Exception ex)
            {
                LogCsv("FS", "ReadFailed", fileName, 0, $"Error: {ex.Message}");
            }
        }

        private static void PrintPreview(string fileName, byte[] data)
        {
            int previewLength = Math.Min(data.Length, PreviewByteCount);
            StringBuilder preview = new StringBuilder(previewLength);

            for (int i = 0; i < previewLength; i++)
            {
                byte b = data[i];
                if (b >= 32 && b <= 126) 
                {
                    preview.Append((char)b);
                }
                else 
                {
                    preview.Append('.');
                }
            }

            Console.WriteLine($"\n--- PREVIEW: {fileName} ({data.Length} bytes total) ---");
            Console.WriteLine(preview.ToString());
            Console.WriteLine("--------------------------------------------------\n");
        }

        private static long GetSafeFileSize(string filePath)
        {
            try
            {
                if (File.Exists(filePath))
                {
                    return new FileInfo(filePath).Length;
                }
            }
            catch
            {
                // File might be locked or already deleted
            }
            return 0;
        }

        private static void LogCsv(string layer, string eventType, string identifier, long size, string details)
        {
            string timestamp = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss.fff");
            string safeDetails = $"\"{details.Replace("\"", "\"\"")}\"";
            string csvLine = $"{timestamp},{layer},{eventType},{identifier},{size},{safeDetails}";
            
            Console.WriteLine($"[{timestamp}] {layer,-3} | {eventType,-15} | {identifier,-12} | Size: {size,-6} | {details}");
            
            lock (_logLock)
            {
                try
                {
                    File.AppendAllText(LogFilePath, csvLine + "\n");
                }
                catch
                {
                    // Failsafe for file logging issues to prevent crashing the observer
                }
            }
        }

        private static void LogConsole(string layer, string eventType, string message)
        {
            string timestamp = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss.fff");
            Console.WriteLine($"[{timestamp}] {layer,-3} | {eventType,-15} | {message}");
        }
    }
}