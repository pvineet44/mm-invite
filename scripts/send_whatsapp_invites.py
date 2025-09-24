#!/usr/bin/env python3
"""Send personalised invite PDFs over WhatsApp via the Interakt API with template."""

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
DEFAULT_ENV_FILE = ROOT_DIR / ".env"
DEFAULT_TEMPLATE_NAME = "mm_invite_v2"
DEFAULT_TEMPLATE_LANGUAGE = "en"
DEFAULT_HEADER_IMAGE = "https://mm.purebillion.tech/pdfs/header.png"
DEFAULT_PDF_API_URL = "http://127.0.0.1:8000/api/generate-pdf"

FIELD_FALLBACKS = {
    "display_name": ("display_name", "Display Name", "name", "Name", "full_name", "fullName"),
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
    parser.add_argument("--resume-from", dest="resume_from", default=None)
    parser.add_argument("--dry-run", dest="dry_run", action="store_true")
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
        help="Interakt template name (default: mm_invite_v2).",
    )
    parser.add_argument(
        "--template-language",
        dest="template_language",
        default=DEFAULT_TEMPLATE_LANGUAGE,
        help="Template language code (default: en).",
    )
    parser.add_argument(
        "--header-image",
        dest="header_image",
        default=DEFAULT_HEADER_IMAGE,
        help="URL of the header image for the template.",
    )
    parser.add_argument(
        "--pdf-api-url",
        dest="pdf_api_url",
        default=os.environ.get("PDF_API_URL", DEFAULT_PDF_API_URL),
        help="Endpoint for the Laravel PDF generation API.",
    )
    parser.add_argument(
        "--callback-data",
        dest="callback_data",
        default="",
        help="Optional callbackData value echoed by Interakt webhooks.",
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
                display_name = pick_first(record, FIELD_FALLBACKS["display_name"])
                phone = pick_first(record, FIELD_FALLBACKS["phone"])
                country_code = pick_first(record, FIELD_FALLBACKS["country_code"]) or "91"

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
    def __init__(self, api_key: str, endpoint: str = API_ENDPOINT) -> None:
        self.api_key = api_key
        self.endpoint = endpoint

    @staticmethod
    def _format_country_code(country_code: str) -> str:
        return country_code if country_code.startswith("+") else f"+{country_code}"

    def send_template_with_button(
        self,
        *,
        country_code: str,
        phone_number: str,
        template_name: str,
        template_language: str,
        header_image_url: str,
        button_url: str,
        callback_data: str = "",
    ) -> Dict[str, object]:
        """Send a template message with image header and button with dynamic URL."""

        # Prepare the template payload
        template_payload = {
            "name": template_name,
            "languageCode": template_language,
            "headerValues": [
                header_image_url  # Image URL for the header
            ],
            # No bodyValues needed as the template has no placeholders
        }

        # Add button action if we have a button URL
        if button_url:
            template_payload["buttonValues"] = {
                "0": [button_url]  # Button index 0 gets the URL
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
    resume_from: Optional[str] = args.resume_from
    dry_run: bool = args.dry_run
    env_file: Path = args.env_file
    template_name: str = args.template_name
    template_language: str = args.template_language
    header_image_url: str = args.header_image
    callback_data = args.callback_data.strip()
    pdf_api_url = args.pdf_api_url.strip() or os.environ.get("PDF_API_URL", DEFAULT_PDF_API_URL)

    load_env_file(env_file)

    try:
        invitees = read_invitees(csv_path)
    except CsvError as error:
        sys.stderr.write(f"{error}\n")
        return 1

    if not invitees:
        print(f"No rows found in CSV {csv_path}.")
        return 0

    if not pdf_api_url:
        sys.stderr.write("PDF API URL must be provided via --pdf-api-url or PDF_API_URL env.\n")
        return 1

    api_key = os.environ.get("WHATSAPP_API_KEY", "").strip()
    if not dry_run and not api_key:
        sys.stderr.write("WHATSAPP_API_KEY must be set unless --dry-run is enabled.\n")
        return 1

    client = (
        InteraktClient(api_key)
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

        try:
            # Generate PDF for this invitee
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

        pdf_url = pdf_result["url"]
        # Extract just the filename - WhatsApp template already has base path configured
        pdf_filename = pdf_result["path"].split("/")[-1] if "/" in pdf_result["path"] else pdf_result["path"]

        if dry_run:
            print(
                f"[dry-run] Would send template '{template_name}' to {invitee.country_code} {invitee.phone}\n"
                f"  Header image: {header_image_url}\n"
                f"  Button filename: {pdf_filename}"
            )
            summary["sent"] += 1
            continue

        try:
            assert client is not None  # for type-checkers

            result = client.send_template_with_button(
                country_code=invitee.country_code,
                phone_number=invitee.phone,
                template_name=template_name,
                template_language=template_language,
                header_image_url=header_image_url,
                button_url=pdf_filename,  # Use just filename, WhatsApp will prepend base URL
                callback_data=callback_data,
            )

            print(f"Sent template to {invitee.country_code} {invitee.phone} with PDF: {pdf_filename}")

            # Log the API response for debugging
            if "result" in result and not result.get("result"):
                sys.stderr.write(f"  API Response: {json.dumps(result, indent=2)}\n")

            summary["sent"] += 1
        except Exception as exc:  # pylint: disable=broad-except
            sys.stderr.write(
                f"Failed to send template to {invitee.country_code} {invitee.phone}: {exc}\n"
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