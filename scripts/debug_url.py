#!/usr/bin/env python3
"""Debug the URL issue"""

import json
from send_whatsapp_invites import generate_pdf_via_api

# Test PDF generation
pdf_result = generate_pdf_via_api("http://127.0.0.1:8000/api/generate-pdf", text="Debug Test")
print("PDF API Result:")
print(json.dumps(pdf_result, indent=2))
print(f"\nURL from API: {pdf_result['url']}")
print(f"Path from API: {pdf_result['path']}")

# Check if there's any URL manipulation
pdf_url = pdf_result["url"]
print(f"\nFinal URL to be sent: {pdf_url}")