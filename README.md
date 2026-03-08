\# RCPT



Digital receipt infrastructure for physical retail.



RCPT allows customers to \*\*tap their phone after paying and instantly receive a digital receipt\*\* stored in a personal receipt vault.



The system captures printed receipts directly from the POS printing pipeline and converts them into structured digital receipts.



Live prototype:



https://rcpt.digital



---



\# What RCPT Does (15-Second Explanation)



Today most receipts are still printed on thermal paper.



RCPT replaces that experience with a \*\*tap-to-receive digital receipt\*\*.



Customer flow:



```

Customer pays

&nbsp;     ↓

Receipt prints

&nbsp;     ↓

Customer taps NFC tag

&nbsp;     ↓

Receipt appears in their digital vault

```



No apps required.

No POS integration required.



The system works by \*\*intercepting receipt data before it reaches the printer\*\*.



---



\# Architecture



```

POS Printer

&nbsp;    ↓

Windows Print Spool

&nbsp;    ↓

RCPT Bridge (C# Observer)

&nbsp;    ↓

Receipt Parser

&nbsp;    ↓

FastAPI Backend

&nbsp;    ↓

Receipt Vault

```



\### Flow Explanation



1\. A POS system prints a receipt.

2\. The Windows print spooler writes the print job.

3\. \*\*RCPT Bridge\*\* detects the spool file.

4\. The receipt data is parsed and structured.

5\. Parsed receipt JSON is sent to the backend API.

6\. The backend stores the receipt.

7\. Customers can tap an NFC tag to claim the receipt.



---



\# Components



\## Backend



FastAPI service responsible for:



\* ingesting receipt data

\* idempotent storage

\* device-based receipt vault

\* receipt claim flow

\* receipt rendering



Location:



```

main.py

```



Technologies:



\* Python

\* FastAPI

\* SQLite

\* Uvicorn



---



\## Bridge



Windows spool observer that captures receipt print jobs and forwards them to the backend.



Location:



```

RcptObserver/

```



Responsibilities:



\* watch Windows spool directory

\* extract receipt text

\* parse receipt structure

\* generate JSON payload

\* send receipt to backend API



Technologies:



\* C#

\* .NET 8

\* Windows spool monitoring



---



\## Receipt Parser



The parser extracts structured data from raw receipt text.



Fields extracted include:



\* merchant name

\* purchase date

\* line items

\* totals

\* tax

\* payment method (if available)



The parsed receipt is converted into structured JSON before being sent to the backend.



---



\# Infrastructure



The RCPT MVP uses the following infrastructure:



\### Backend Hosting



Hosted on:



Render



The FastAPI backend is deployed as a web service.



---



\### Email Delivery



Transactional emails are handled using:



Resend



Used for:



\* sending digital receipts

\* receipt sharing

\* device verification emails



---



\### Domain



Prototype domain:



https://rcpt.digital



---



\# API Overview



Key backend endpoints include:



```

POST /api/bridge/receipt

```



Receives parsed receipts from the RCPT Bridge.



```

GET /t/{terminal\_id}

```



Customer tap page used to claim the most recent receipt.



```

POST /claim

```



Associates a receipt with a device vault.



```

GET /vault

```



Displays stored receipts for a device.



---



\# Development



\## Run Backend



Start the FastAPI server:



```

uvicorn main:app --reload

```



Server runs at:



```

http://127.0.0.1:8000

```



---



\## Run Bridge



Navigate to the observer directory:



```

cd RcptObserver

dotnet run

```



The bridge will begin watching the Windows spool directory and forwarding receipts.



---



\# Repository Structure



```

rcpt-mvp

│

├ main.py

├ requirements.txt

├ render.yaml

├ rcpt.db

├ README.md

├ .gitignore

│

└ RcptObserver

&nbsp;    ├ Program.cs

&nbsp;    ├ RcptObserver.csproj

&nbsp;    ├ bin/

&nbsp;    └ obj/

```



---



\# Current MVP Features



The current prototype supports:



\* receipt interception from Windows spool

\* receipt parsing and extraction

\* backend receipt ingestion

\* idempotent receipt storage

\* device-linked receipt vault

\* NFC tap-based receipt claiming



---



\# Future Improvements



Planned improvements:



\* offline bridge queue (store \& forward)

\* receipt deduplication via idempotency keys

\* multi-terminal printer support

\* merchant-specific parsing templates

\* LLM fallback parsing for unknown receipt layouts

\* production-grade observability



---



\# Status



This repository represents the \*\*initial infrastructure prototype\*\* for the RCPT digital receipt system.



The current focus is validating the end-to-end pipeline:



```

Printer → Bridge → API → Vault → Customer Claim

```



Once stable, the next phase will focus on reliability and scaling.



