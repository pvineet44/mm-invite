#!/usr/bin/env python3
"""Test sending a single WhatsApp invite to verify the setup."""

import sys
import os
from pathlib import Path

# Add parent directory to path to import the main script
sys.path.insert(0, str(Path(__file__).parent))

from send_whatsapp_invites import (
    InteraktClient,
    generate_pdf_via_api,
    load_env_file
)

def main():
    # Load environment variables
    env_file = Path(__file__).parent.parent / ".env"
    load_env_file(env_file)

    # Get API key
    api_key = os.environ.get("WHATSAPP_API_KEY", "").strip()
    if not api_key:
        print("Error: WHATSAPP_API_KEY not found in .env file")
        return 1

    # Test configuration
    test_name = "Test User"
    test_phone = input("Enter phone number to test (without country code): ").strip()
    if not test_phone:
        print("No phone number provided, exiting.")
        return 1

    test_country_code = "91"
    template_name = "mm_invite_v2"
    template_language = "en"
    header_image_url = "https://mm.purebillion.tech/pdfs/header.png"
    pdf_api_url = "http://127.0.0.1:8000/api/generate-pdf"

    print(f"\nTest Configuration:")
    print(f"  Name: {test_name}")
    print(f"  Phone: +{test_country_code} {test_phone}")
    print(f"  Template: {template_name}")
    print(f"  Header Image: {header_image_url}")

    confirm = input("\nProceed with test? (yes/no): ").strip().lower()
    if confirm != "yes":
        print("Test cancelled.")
        return 0

    try:
        # Generate PDF
        print("\nGenerating PDF...")
        pdf_result = generate_pdf_via_api(pdf_api_url, text=test_name)
        pdf_url = pdf_result["url"]
        # Extract just the filename - WhatsApp template already has base path configured
        pdf_filename = pdf_result["path"].split("/")[-1] if "/" in pdf_result["path"] else pdf_result["path"]
        print(f"  PDF generated: {pdf_url}")
        print(f"  Button filename: {pdf_filename}")

        # Send WhatsApp message
        print("\nSending WhatsApp message...")
        client = InteraktClient(api_key)
        result = client.send_template_with_button(
            country_code=test_country_code,
            phone_number=test_phone,
            template_name=template_name,
            template_language=template_language,
            header_image_url=header_image_url,
            button_url=pdf_filename,  # Use just filename, WhatsApp will prepend base URL
            callback_data=""
        )

        print(f"\nAPI Response:")
        import json
        print(json.dumps(result, indent=2))

        if result.get("result"):
            print("\n✓ Message sent successfully!")
        else:
            print("\n✗ Message sending failed. Check the response above.")

    except Exception as e:
        print(f"\nError occurred: {e}")
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())