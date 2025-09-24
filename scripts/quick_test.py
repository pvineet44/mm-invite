#!/usr/bin/env python3
"""Quick test to send a single WhatsApp invite"""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from send_whatsapp_invites import (
    InteraktClient,
    generate_pdf_via_api,
    load_env_file
)

# Configuration - EDIT THIS
TEST_PHONE = "9819645740"  # Change this to your test number
TEST_NAME = "Test User"
TEST_COUNTRY_CODE = "91"

def main():
    # Load environment variables
    env_file = Path(__file__).parent.parent / ".env"
    load_env_file(env_file)

    # Get API key
    api_key = os.environ.get("WHATSAPP_API_KEY", "").strip()
    if not api_key:
        print("Error: WHATSAPP_API_KEY not found in .env file")
        return 1

    # Configuration
    template_name = "mm_invite_v2"
    template_language = "en"
    header_image_url = "https://mm.purebillion.tech/pdfs/header.png"
    pdf_api_url = "http://127.0.0.1:8000/api/generate-pdf"

    print(f"Testing with:")
    print(f"  Name: {TEST_NAME}")
    print(f"  Phone: +{TEST_COUNTRY_CODE} {TEST_PHONE}")
    print(f"  Template: {template_name}")

    try:
        # Generate PDF
        print("\nGenerating PDF...")
        pdf_result = generate_pdf_via_api(pdf_api_url, text=TEST_NAME)
        pdf_filename = pdf_result["path"].split("/")[-1]
        print(f"  PDF URL: {pdf_result['url']}")
        print(f"  Button filename: {pdf_filename}")

        # Send WhatsApp message
        print("\nSending WhatsApp message...")
        client = InteraktClient(api_key)
        result = client.send_template_with_button(
            country_code=TEST_COUNTRY_CODE,
            phone_number=TEST_PHONE,
            template_name=template_name,
            template_language=template_language,
            header_image_url=header_image_url,
            button_url=pdf_filename,
            callback_data=""
        )

        # Check result
        if result.get("result"):
            print("\n✅ SUCCESS! Message sent!")
            print(f"Message ID: {result.get('id', 'N/A')}")
        else:
            print("\n❌ FAILED! Message not sent")
            import json
            print("API Response:")
            print(json.dumps(result, indent=2))

    except Exception as e:
        print(f"\n❌ Error: {e}")
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())