#!/usr/bin/env python3
"""Send personalised invite PDFs over WhatsApp via the Interakt API."""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
from urllib import error, request
from urllib.parse import quote

API_ENDPOINT = "https://api.interakt.ai/v1/public/message/"
ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CSV = ROOT_DIR / "csvs" / "test.csv"
DEFAULT_PDF_DIR = ROOT_DIR / "pdfs"
DEFAULT_ENV_FILE = ROOT_DIR / ".env"
DEFAULT_TEMPLATE_NAME = None
DEFAULT_TEMPLATE_LANGUAGE = "en"
DEFAULT_MEDIA_BASE_URL = "https://mm.purebillion.tech/pdfs/"
DEFAULT_DOCUMENT_MESSAGE = ""

FIELD_FALLBACKS = {
    "display_name": ("display_name", "Display Name", "name", "Name", "full_name", "fullName"),
    "first_name": ("first_name", "firstName", "firstname"),
    "last_name": ("last_name", "lastName", "lastname"),
    "gender": ("gender", "salutation"),
    "phone": ("phone", "mobileNo", "mobile"),
    "country_code": ("country_code", "countryCode", "isdCode"),
    "pdf_file": ("pdf_file", "pdfFile", "pdf_name", "pdfName", "pdf_filename", "pdfFilename"),
}


@dataclass
class Invitee:
    line_no: int
    phone: str
    country_code: str
    display_name: str
    pdf_override: Optional[str] = None

    def pdf_file_name(self) -> str:
        base_name = self.pdf_override.strip() if self.pdf_override else self.display_name.strip()
        if not base_name:
            raise ValueError("Invitee lacks sufficient information to derive PDF file name")
        return self._ensure_pdf_suffix(base_name)

    def pdf_path(self, directory: Path) -> Path:
        return directory / self.pdf_file_name()

    @staticmethod
    def _ensure_pdf_suffix(name: str) -> str:
        return name if name.lower().endswith(".pdf") else f"{name}.pdf"


class CsvError(RuntimeError):
    """Raised when we cannot read or interpret the CSV file."""


def load_env_file(env_path: Path) -> None:
    """Populate os.environ with variables from a .env-style file if present."""

    try:
        text = env_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return
    except OSError as exc:
        sys.stderr.write(f"Warning: unable to read env file {env_path}: {exc}\n")
        return

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]
        os.environ.setdefault(key, value)


def parse_arguments(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", dest="csv_path", default=DEFAULT_CSV, type=Path)
    parser.add_argument("--pdf-dir", dest="pdf_dir", default=DEFAULT_PDF_DIR, type=Path)
    parser.add_argument("--resume-from", dest="resume_from", default=None)
    parser.add_argument("--dry-run", dest="dry_run", action="store_true")
    parser.add_argument(
        "--media-base-url",
        dest="media_base_url",
        default=os.environ.get("WHATSAPP_MEDIA_BASE_URL", DEFAULT_MEDIA_BASE_URL),
        help="Base URL used to build mediaUrl for PDFs.",
    )
    parser.add_argument(
        "--document-message",
        dest="document_message",
        default=os.environ.get("WHATSAPP_DOCUMENT_MESSAGE", DEFAULT_DOCUMENT_MESSAGE),
        help="Optional WhatsApp message to accompany document sends.",
    )
    parser.add_argument(
        "--callback-data",
        dest="callback_data",
        default=os.environ.get("WHATSAPP_CALLBACK_DATA", ""),
        help="Optional callbackData value echoed by Interakt webhooks.",
    )
    parser.add_argument(
        "--env-file",
        dest="env_file",
        type=Path,
        default=DEFAULT_ENV_FILE,
        help="Load environment variables from this file before running.",
    )
    parser.add_argument(
        "--template-name",
        dest="template_name",
        default=DEFAULT_TEMPLATE_NAME,
        help="Send using an Interakt template (e.g. gifting_gyaan).",
    )
    parser.add_argument(
        "--template-language",
        dest="template_language",
        default=DEFAULT_TEMPLATE_LANGUAGE,
        help="Template language code (default: en).",
    )
    parser.add_argument(
        "--template-body-values",
        dest="template_body_values",
        default="",
        help="Comma-separated values for template body placeholders (if any).",
    )
    return parser.parse_args(argv)


def pick_first(record: Dict[str, str], keys: Tuple[str, ...]) -> str:
    for key in keys:
        value = record.get(key)
        if value:
            return value.strip()
    return ""


def read_invitees(csv_path: Path) -> List[Invitee]:
    try:
        with csv_path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                raise CsvError("CSV has no header row")
            invitees: List[Invitee] = []
            for index, row in enumerate(reader, start=2):  # account for header
                record = {key: (value or "").strip() for key, value in row.items() if key}
                first = pick_first(record, FIELD_FALLBACKS.get("first_name", ()))
                last = pick_first(record, FIELD_FALLBACKS.get("last_name", ()))
                gender = pick_first(record, FIELD_FALLBACKS.get("gender", ()))
                display_name = pick_first(record, FIELD_FALLBACKS["display_name"])
                pdf_override = pick_first(record, FIELD_FALLBACKS["pdf_file"]) or None
                phone = pick_first(record, FIELD_FALLBACKS["phone"])
                country_code = pick_first(record, FIELD_FALLBACKS["country_code"]) or "+91"

                if not display_name and (first or last or gender):
                    first_gender = f"{first}{gender}".strip()
                    parts = ["Shri", first_gender, last]
                    display_name = " ".join(part for part in parts if part).strip()

                invitees.append(
                    Invitee(
                        line_no=index,
                        phone=phone,
                        country_code=normalise_country_code(country_code),
                        display_name=display_name.strip(),
                        pdf_override=pdf_override,
                    )
                )
    except FileNotFoundError as exc:
        raise CsvError(f"CSV file not found at {csv_path}") from exc
    except OSError as exc:
        raise CsvError(f"Failed reading CSV {csv_path}: {exc}") from exc

    return invitees


def normalise_country_code(code: str) -> str:
    code = code.strip()
    if not code:
        return "91"
    # Interakt expects country codes without a leading plus sign.
    return code[1:] if code.startswith("+") else code


def parse_body_values(raw: str) -> List[str]:
    if not raw:
        return []
    return [value.strip() for value in raw.split(",")]


class InteraktClient:
    def __init__(self, api_key: str, endpoint: str = API_ENDPOINT, *, media_base_url: str) -> None:
        self.api_key = api_key
        self.endpoint = endpoint
        self.media_base_url = media_base_url

    def build_media_url(self, file_name: str) -> str:
        return f"{self.media_base_url}{quote(file_name)}"

    @staticmethod
    def _format_country_code(country_code: str) -> str:
        return country_code if country_code.startswith("+") else f"+{country_code}"

    def send_document(
        self,
        *,
        country_code: str,
        phone_number: str,
        pdf_path: Path,
        message: str,
        callback_data: str,
    ) -> Dict[str, object]:
        file_name = pdf_path.name
        media_url = self.build_media_url(file_name)

        payload = {
            "countryCode": self._format_country_code(country_code),
            "phoneNumber": phone_number,
            "type": "Document",
            "data": {
                "mediaUrl": media_url,
            },
        }

        if message:
            payload["data"]["message"] = message
        if callback_data:
            payload["callbackData"] = callback_data

        body = json.dumps(payload).encode("utf-8")

        request_obj = request.Request(
            self.endpoint,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Basic {self.api_key}",
                "Content-Type": "application/json",
            },
        )

        try:
            with request.urlopen(request_obj) as response:
                payload = response.read()
                charset = response.headers.get_content_charset("utf-8")
                text = payload.decode(charset)
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    return {"status": response.status, "body": text}
        except error.HTTPError as exc:
            error_payload = exc.read()  # type: ignore[attr-defined]
            try:
                error_text = error_payload.decode("utf-8", "replace")
            except Exception:  # pylint: disable=broad-except
                error_text = "<unable to decode error payload>"
            raise RuntimeError(
                f"Interakt API responded with {exc.code} {exc.reason}: {error_text}"
            ) from exc

    def send_template_document(
        self,
        *,
        country_code: str,
        phone_number: str,
        pdf_path: Path,
        template_name: str,
        template_language: str,
        body_values: List[str],
        callback_data: str,
    ) -> Dict[str, object]:
        file_name = pdf_path.name
        media_url = self.build_media_url(file_name)

        template_payload = {
            "name": template_name,
            "languageCode": template_language,
            "bodyValues": body_values,
            "headerValues": [media_url],
            "fileName": file_name,
        }

        payload = {
            "countryCode": self._format_country_code(country_code),
            "phoneNumber": phone_number,
            "type": "Template",
            "template": template_payload,
        }

        if callback_data:
            payload["callbackData"] = callback_data

        body = json.dumps(payload).encode("utf-8")

        request_obj = request.Request(
            self.endpoint,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Basic {self.api_key}",
                "Content-Type": "application/json",
            },
        )

        try:
            with request.urlopen(request_obj) as response:
                payload = response.read()
                charset = response.headers.get_content_charset("utf-8")
                text = payload.decode(charset)
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    return {"status": response.status, "body": text}
        except error.HTTPError as exc:
            error_payload = exc.read()  # type: ignore[attr-defined]
            try:
                error_text = error_payload.decode("utf-8", "replace")
            except Exception:  # pylint: disable=broad-except
                error_text = "<unable to decode error payload>"
            raise RuntimeError(
                f"Interakt API responded with {exc.code} {exc.reason}: {error_text}"
            ) from exc


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = parse_arguments(argv)

    csv_path: Path = args.csv_path
    pdf_dir: Path = args.pdf_dir
    resume_from: Optional[str] = args.resume_from
    dry_run: bool = args.dry_run
    env_file: Path = args.env_file
    template_name: Optional[str] = args.template_name
    template_language: str = args.template_language
    template_body_values = parse_body_values(args.template_body_values)
    media_base_url = args.media_base_url.strip() or DEFAULT_MEDIA_BASE_URL
    if not media_base_url.endswith("/"):
        media_base_url = f"{media_base_url}/"
    document_message = args.document_message.strip()
    callback_data = args.callback_data.strip()

    load_env_file(env_file)

    try:
        invitees = read_invitees(csv_path)
    except CsvError as error:
        sys.stderr.write(f"{error}\n")
        return 1

    if not invitees:
        print(f"No rows found in CSV {csv_path}.")
        return 0

    if not pdf_dir.is_dir():
        sys.stderr.write(f"PDF directory not found: {pdf_dir}\n")
        return 1

    api_key = os.environ.get("WHATSAPP_API_KEY", "").strip()
    if not dry_run and not api_key:
        sys.stderr.write("WHATSAPP_API_KEY must be set unless --dry-run is enabled.\n")
        return 1

    client = (
        InteraktClient(
            api_key,
            media_base_url=media_base_url,
        )
        if not dry_run
        else None
    )

    summary = {
        "total": len(invitees),
        "processed": 0,
        "sent": 0,
        "skipped": 0,
        "failed": 0,
    }

    resume_ready = resume_from is None

    for invitee in invitees:
        summary["processed"] += 1

        if not invitee.display_name:
            sys.stderr.write(
                f"Skipping line {invitee.line_no}: missing name information.\n"
            )
            summary["skipped"] += 1
            continue

        if not invitee.phone:
            sys.stderr.write(
                f"Skipping {invitee.display_name or 'unknown name'} (line {invitee.line_no}): missing phone.\n"
            )
            summary["skipped"] += 1
            continue

        if not resume_ready:
            if invitee.phone == resume_from:
                resume_ready = True
            else:
                summary["skipped"] += 1
                continue

        pdf_path = invitee.pdf_path(pdf_dir)
        if not pdf_path.is_file():
            sys.stderr.write(
                f"PDF not found for {invitee.display_name or 'unknown name'} (expected at {pdf_path}).\n"
            )
            summary["failed"] += 1
            continue

        if dry_run:
            mode = "template" if template_name else "document"
            extra = []
            if document_message and not template_name:
                extra.append(f"message='{document_message}'")
            if callback_data:
                extra.append(f"callbackData='{callback_data}'")
            extra_suffix = f" ({', '.join(extra)})" if extra else ""
            print(
                f"[dry-run] Would send {pdf_path.name} ({mode}) to {invitee.country_code} {invitee.phone}{extra_suffix}."
            )
            summary["sent"] += 1
            continue

        try:
            assert client is not None  # for type-checkers
            if template_name:
                client.send_template_document(
                    country_code=invitee.country_code,
                    phone_number=invitee.phone,
                    pdf_path=pdf_path,
                    template_name=template_name,
                    template_language=template_language,
                    body_values=template_body_values,
                    callback_data=callback_data,
                )
            else:
                client.send_document(
                    country_code=invitee.country_code,
                    phone_number=invitee.phone,
                    pdf_path=pdf_path,
                    message=document_message,
                    callback_data=callback_data,
                )
            print(f"Sent {pdf_path.name} to {invitee.country_code} {invitee.phone}.")
            summary["sent"] += 1
        except Exception as exc:  # pylint: disable=broad-except
            sys.stderr.write(
                f"Failed to send {pdf_path.name} to {invitee.country_code} {invitee.phone}: {exc}\n"
            )
            summary["failed"] += 1

    print("\nSummary\n=======")
    print(f"Total rows: {summary['total']}")
    print(f"Processed : {summary['processed']}")
    print(f"Sent      : {summary['sent']}")
    print(f"Skipped   : {summary['skipped']}")
    print(f"Failed    : {summary['failed']}")

    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
