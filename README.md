# WhatsApp PDF Sender

Automation helper that reads invite details from a CSV, finds the matching personalised PDF, and sends it to each contact using the Interakt public API.

## Prerequisites

- Python 3.9+ (tested with Python 3.13).
- CSV file in `csvs/` (testing default: `csvs/test.csv`).
- Personalised PDFs stored in `pdfs/` and named `Shri <first><gender> <last>.pdf` (e.g. `Shri PradipBhai Mehta.pdf`).
- Interakt API key available as `WHATSAPP_API_KEY` (set via `.env` or environment export).

## Python Script

```
python3 scripts/send_whatsapp_docs.py --dry-run
```

This validates CSV parsing, PDF lookup, and prints the actions without calling the API.

For live sends, create a `.env` in the project root or export the variable manually:

```
WHATSAPP_API_KEY=base64-credential
```

Then run:

```
python3 scripts/send_whatsapp_docs.py
```

Optional flags:

- `--csv <path>`: custom CSV file (default `csvs/test.csv`).
- `--pdf-dir <dir>`: personalised PDFs directory (default `pdfs/`).
- `--resume-from <phone>`: skip rows until the phone number matches, then resume sending.
- `--dry-run`: keep the script in validation mode.
- `--template-name <id>`: send via an Interakt template (e.g. `gifting_gyaan`).
- `--template-language <code>`: override the template language (default `en`).
- `--template-body-values <v1,v2>`: comma-separated values for body placeholders, if your template uses them.
- `--env-file <path>`: custom `.env` file (defaults to project root `/.env`).
- `--env-file <path>`: custom `.env` file (defaults to project root `/.env`).

## CSV Columns

The script looks for the following column names (case-sensitive) and falls back to common alternatives:

- `first_name` (`firstName`, `firstname`)
- `last_name` (`lastName`, `lastname`)
- `gender` (`salutation`)
- `phone` (`mobileNo`, `mobile`)
- `country_code` (`countryCode`, `isdCode`)

Rows missing the required values are skipped with an error message.

## Interakt Payload

By default the helper posts multipart form data to `https://api.interakt.ai/v1/public/message/` with `type = Document` and the PDF attached as `documentFile`.

When `--template-name` is supplied, the script switches to a template send: it posts `type = Template`, attaches the PDF, and includes your template metadata as a JSON payload in the `template` field. Update `send_template_document` in `scripts/send_whatsapp_docs.py` if Interakt expects different field names for document headers in your workspace.

## Node Variant (Optional)

A Node.js implementation remains available via `npm run send:whatsapp`. It follows the same CSV/PDF conventions and command-line flags.
