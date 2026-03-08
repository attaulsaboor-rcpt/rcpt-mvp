\# RCPT MVP



Prototype infrastructure for intercepting POS receipts and converting them into digital receipts.



The system captures printed receipts directly from the Windows print spooler, parses them, and forwards them to a backend service where customers can claim them into a digital receipt vault.



---



\# Architecture



```

POS Printer

&nbsp;   ↓

Windows Print Spool

&nbsp;   ↓

RCPT Bridge (C# Observer)

&nbsp;   ↓

Receipt Parser

&nbsp;   ↓

FastAPI Backend

&nbsp;   ↓

Receipt Vault

```



\### Flow Explanation



1\. A POS system prints a receipt.

2\. The Windows print spooler writes the receipt job to disk.

3\. \*\*RCPT Bridge\*\* detects the new spool file.

4\. The bridge parses the receipt data.

5\. Parsed receipt JSON is sent to the backend API.

6\. The backend stores the receipt.

7\. Customers can tap an NFC tag to claim the receipt into their vault.



---



\# Components



\## Backend



FastAPI service responsible for:



\* ingesting receipt data

\* idempotent storage

\* device-based vault

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

\* Windows print spool monitoring



---



\## Receipt Parser



The parser extracts structured data from raw receipt text.



Fields extracted:



\* merchant name

\* date

\* items

\* totals

\* tax (if present)

\* payment method (if present)



The parsed receipt is converted into structured JSON before being sent to the backend.



---



\# Development



\## Run Backend



Start the FastAPI server:



```

uvicorn main:app --reload

```



The API will run locally on:



```

http://127.0.0.1:8000

```



---



\## Run Bridge



Navigate to the observer directory and start the daemon:



```

cd RcptObserver

dotnet run

```



The bridge will begin watching the Windows spool directory and forwarding receipts to the backend.



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

\* NFC tap-based receipt claiming

\* device-linked receipt vault



---



\# Future Improvements



Planned improvements include:



\* bridge offline queue (store \& forward)

\* receipt deduplication using idempotency keys

\* multi-terminal printer support

\* improved receipt parsing templates

\* LLM fallback parsing for unknown receipt formats

\* production deployment pipeline



---



\# Status



This repository represents the \*\*early infrastructure prototype\*\* for the RCPT digital receipt system.



The current focus is validating the end-to-end pipeline:



```

Printer → Bridge → API → Vault → Customer Claim

```



Once the pipeline is fully stable, the next phase will focus on reliability and scaling.



