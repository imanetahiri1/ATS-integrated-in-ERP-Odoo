#  ATS Intelligent — Odoo ERP

An intelligent Applicant Tracking System (ATS) built as a business plugin extending Odoo's native Recruitment module, transforming a fully manual hiring process into an AI-driven automated pipeline.

---

## Architecture

Two interconnected components via a secured REST API:

- **RHS Talent Platform** — multi-source CV collection (LinkedIn, MarocAnnonces, RHS Emploi), AI-based text extraction, unified CV database.
- **ATS Plugin (Odoo)** — semantic skill extraction via NLP, hybrid scoring engine (deterministic algorithms + Google Gemini), automatic Kanban pipeline transitions.

---

## Key Features

- CV analyzed in under 10 seconds
- 30+ structured fields extracted (skills, experience, education, languages)
- Compatibility score out of 100
- AI-generated justified recommendations
- Automated candidate shortlisting
- Full traceability of every decision

---

## Resilience & Fallbacks

| Failure scenario | Fallback behavior |
|---|---|
| Scanned / low-quality CV | OCR pipeline (Tesseract + pdf2image) with manual review option in Odoo |
| Gemini API unavailable | Deterministic scoring only — pipeline never stops |
| RHS Talent Platform unreachable | Manual CV upload directly into the ATS module |
| Non-French/English CV | Partial extraction with flagged confidence score |

---

## Tech Stack

`Python` · `Odoo 18` · `Google Gemini` · `NLP` · `Tesseract OCR` · `pdfplumber` · `python-docx` · `REST API`
