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
from urllib.parse import quote, urlparse

API_ENDPOINT = "https://api.interakt.ai/v1/public/message/"
ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CSV = ROOT_DIR / "csvs" / "test.csv"
DEFAULT_PDF_DIR = ROOT_DIR / "pdfs"
DEFAULT_ENV_FILE = ROOT_DIR / ".env"
DEFAULT_TEMPLATE_NAME = "mm_utility_template"
DEFAULT_TEMPLATE_LANGUAGE = "en"
DEFAULT_MEDIA_BASE_URL = "https://mm.purebillion.tech/pdfs/"
DEFAULT_DOCUMENT_MESSAGE = ""
DEFAULT_PDF_API_URL = "http://127.0.0.1:8000/api/generate-pdf"
HARDCODED_BODY_TEXT = (
    "Manavta Mahotsav 2025\n\n"
    "Rashtrasant Param Gurudev Shree Namramuni Maharaj Saheb's 55th Janmotsav\n"
    "Shree Uvasaggaharam Mantrotsav\n\n"
    "\U0001F4C5 28th September, 2025 | Girnar\n"
    "\U0001F558 9.00 am onwards"
)
HARDCODED_BODY_VALUES = [HARDCODED_BODY_TEXT]

FIELD_FALLBACKS = {
    "display_name": ("display_name", "Display Name", "name", "Name", "full_name", "fullName"),
    "first_name": ("first_name", "firstName", "firstname"),
    "last_name": ("last_name", "lastName", "lastname"),
    "gender": ("gender", "salutation"),
    "phone": ("phone", "mobileNo", "mobile"),
    "country_code": ("country_code", "countryCode", "isdCode"),
}


@dataclass
class Invitee:
    line_no: int
    phone: str
    country_code: str
    display_name: str


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
        "--campaign-id",
        dest="campaign_id",
        default=os.environ.get("WHATSAPP_CAMPAIGN_ID", ""),
        help="Optional Interakt campaignId to tag outgoing messages.",
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
    parser.add_argument(
        "--template-button-values",
        dest="template_button_values",
        default="",
        help="Semicolon-separated button value groups (each group comma-separated).",
    )
    parser.add_argument(
        "--pdf-api-url",
        dest="pdf_api_url",
        default=os.environ.get("PDF_API_URL", DEFAULT_PDF_API_URL),
        help="Endpoint for the Laravel PDF generation API.",
    )
    parser.add_argument(
        "--file-url",
        dest="file_url",
        default=os.environ.get("WHATSAPP_STATIC_FILE_URL", ""),
        help="Skip PDF generation and use this pre-generated file URL instead.",
    )
    parser.add_argument(
        "--file-name",
        dest="file_name",
        default=os.environ.get("WHATSAPP_STATIC_FILE_NAME", ""),
        help="Optional file name when using --file-url (defaults to name inferred from URL).",
    )
    parser.add_argument(
        "--header-caption",
        dest="header_caption",
        default=os.environ.get("WHATSAPP_HEADER_CAPTION", ""),
        help="Optional caption shown below the document preview.",
    )
    parser.add_argument(
        "--template-header-url",
        dest="template_header_url",
        default=os.environ.get("WHATSAPP_TEMPLATE_HEADER_URL", ""),
        help="Optional media URL inserted as headerValues[0] (e.g. static image).",
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


def parse_button_values(raw: str) -> List[List[str]]:
    if not raw:
        return []

    groups: List[List[str]] = []
    for chunk in raw.split(";"):
        stripped = chunk.strip()
        if not stripped:
            continue
        group = [value.strip() for value in stripped.split(",") if value.strip()]
        if group:
            groups.append(group)

    return groups


def generate_pdf_via_api(api_url: str, *, text: str) -> Dict[str, str]:
    payload: Dict[str, object] = {"text": text}

    body = json.dumps(payload).encode("utf-8")

    request_obj = request.Request(
        api_url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )

    try:
        with request.urlopen(request_obj) as response:
            response_body = response.read()
            charset = response.headers.get_content_charset("utf-8")
            text_body = response_body.decode(charset)
            try:
                data = json.loads(text_body)
            except json.JSONDecodeError as exc:
                raise RuntimeError(
                    f"PDF API returned non-JSON payload: {text_body[:200]}"
                ) from exc

            if response.status not in (200, 201):
                raise RuntimeError(
                    f"PDF API responded with {response.status}: {data}"
                )

            if "url" not in data or "path" not in data:
                raise RuntimeError(
                    "PDF API response missing required 'url' or 'path' fields"
                )

            return {"url": str(data["url"]), "path": str(data["path"])}
    except error.HTTPError as exc:
        error_payload = exc.read()  # type: ignore[attr-defined]
        try:
            error_text = error_payload.decode("utf-8", "replace")
        except Exception:  # pylint: disable=broad-except
            error_text = "<unable to decode error payload>"
        raise RuntimeError(
            f"PDF API responded with {exc.code} {exc.reason}: {error_text}"
        ) from exc
    except error.URLError as exc:
        raise RuntimeError(f"Failed to reach PDF API at {api_url}: {exc.reason}") from exc

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
        media_url: str,
        file_name: str,
        message: str,
        callback_data: str,
    ) -> Dict[str, object]:
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
                payload_bytes = response.read()
                charset = response.headers.get_content_charset("utf-8")
                text = payload_bytes.decode(charset)
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
        template_name: str,
        template_language: str,
        body_values: List[str],
        media_url: Optional[str] = None,
        file_name: Optional[str] = None,
        caption: str = "",
        callback_data: str = "",
        campaign_id: str = "",
        button_values: Optional[List[List[str]]] = None,
    ) -> Dict[str, object]:
        resolved_button_values = button_values or []

        template_payload: Dict[str, object] = {
            "name": template_name,
            "languageCode": template_language,
            "bodyValues": body_values,
            "buttonValues": resolved_button_values,
        }

        if media_url:
            template_payload["headerValues"] = [media_url]
        if file_name:
            template_payload["fileName"] = file_name
        if caption:
            template_payload["caption"] = caption

        payload: Dict[str, object] = {
            "countryCode": self._format_country_code(country_code),
            "phoneNumber": phone_number,
            "type": "Template",
            "template": template_payload,
        }

        if callback_data:
            payload["callbackData"] = callback_data
        if campaign_id:
            payload["campaignId"] = campaign_id
        payload["buttonValues"] = resolved_button_values

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
                payload_bytes = response.read()
                charset = response.headers.get_content_charset("utf-8")
                text = payload_bytes.decode(charset)
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
    resume_from: Optional[str] = args.resume_from
    dry_run: bool = args.dry_run
    env_file: Path = args.env_file
    template_name: Optional[str] = args.template_name
    template_language: str = args.template_language
    template_body_values = parse_body_values(args.template_body_values)
    template_button_values = parse_button_values(args.template_button_values)
    header_caption: str = args.header_caption.strip()
    static_file_url: str = args.file_url.strip()
    static_file_name: str = args.file_name.strip()
    media_base_url = args.media_base_url.strip() or DEFAULT_MEDIA_BASE_URL
    if not media_base_url.endswith("/"):
        media_base_url = f"{media_base_url}/"
    document_message = args.document_message.strip()
    callback_data = args.callback_data.strip()
    campaign_id = args.campaign_id.strip()
    pdf_api_url = args.pdf_api_url.strip() or os.environ.get("PDF_API_URL", DEFAULT_PDF_API_URL)
    template_header_url = args.template_header_url.strip()

    load_env_file(env_file)

    try:
        invitees = read_invitees(csv_path)
    except CsvError as error:
        sys.stderr.write(f"{error}\n")
        return 1

    if not invitees:
        print(f"No rows found in CSV {csv_path}.")
        return 0

    if not static_file_url and not pdf_api_url:
        sys.stderr.write("Provide either --pdf-api-url or --file-url so we know where to fetch PDFs.\n")
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

        if static_file_url:
            media_url = static_file_url
            if static_file_name:
                file_name = static_file_name
            else:
                parsed = urlparse(static_file_url)
                file_name = Path(parsed.path).name or "invite.pdf"
        else:
            try:
                pdf_result = generate_pdf_via_api(
                    pdf_api_url,
                    text=invitee.display_name or "",
                )
            except Exception as exc:  # pylint: disable=broad-except
                sys.stderr.write(
                    f"Failed to generate PDF for {invitee.display_name or 'unknown name'}: {exc}\n"
                )
                summary["failed"] += 1
                continue

            media_url = pdf_result["url"]
            file_name = Path(pdf_result["path"]).name

        body_values_for_template: Optional[List[str]] = None
        button_values_for_template: Optional[List[List[str]]] = None
        if template_name:
            body_values_for_template = list(HARDCODED_BODY_VALUES)
            button_values_for_template = [group[:] for group in template_button_values] if template_button_values else [[file_name]]

        if dry_run:
            mode = "template" if template_name else "document"
            extra = []
            if document_message and not template_name:
                extra.append(f"message='{document_message}'")
            if callback_data:
                extra.append(f"callbackData='{callback_data}'")
            if campaign_id:
                extra.append(f"campaignId='{campaign_id}'")
            if template_name and template_header_url:
                extra.append(f"headerUrl='{template_header_url}'")
            if template_name and body_values_for_template is not None:
                extra.append(f"bodyValues={body_values_for_template}")
            if template_name and button_values_for_template is not None:
                extra.append(f"buttonValues={button_values_for_template}")
            extra_suffix = f" ({', '.join(extra)})" if extra else ""
            print(
                f"[dry-run] Would send {file_name} ({mode}) from {media_url} to {invitee.country_code} {invitee.phone}{extra_suffix}."
            )
            summary["sent"] += 1
            continue

        try:
            assert client is not None  # for type-checkers
            if template_name:
                assert body_values_for_template is not None
                assert button_values_for_template is not None
                client.send_template_document(
                    country_code=invitee.country_code,
                    phone_number=invitee.phone,
                    template_name=template_name,
                    template_language=template_language,
                    body_values=body_values_for_template,
                    media_url=template_header_url or None,
                    file_name=None,
                    caption=header_caption,
                    callback_data=callback_data,
                    campaign_id=campaign_id,
                    button_values=button_values_for_template,
                )
            else:
                client.send_document(
                    country_code=invitee.country_code,
                    phone_number=invitee.phone,
                    media_url=media_url,
                    file_name=file_name,
                    message=document_message,
                    callback_data=callback_data,
                )
            print(f"Sent {file_name} (from {media_url}) to {invitee.country_code} {invitee.phone}.")
            summary["sent"] += 1
        except Exception as exc:  # pylint: disable=broad-except
            sys.stderr.write(
                f"Failed to send {file_name} to {invitee.country_code} {invitee.phone}: {exc}\n"
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
