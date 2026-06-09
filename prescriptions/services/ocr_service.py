"""
OCR service for extracting prescription data from images.

Pipeline priority:
  1. Azure Form Recognizer (OCR) → Gemini text parsing
  2. Direct Gemini vision (if Azure unavailable)
  3. Mock data (fallback for demo/development)
"""

import base64
import json
import logging
import mimetypes
from django.conf import settings

logger = logging.getLogger(__name__)


def extract_prescription_data(image_file) -> dict:
    """
    Extract prescription data from an uploaded image file.

    Priority: Azure OCR → Gemini Vision → Mock
    """
    raw_text = _extract_text_from_image(image_file)

    if raw_text and raw_text != "Mock: No Azure OCR":
        return _parse_with_gemini(raw_text)

    result = _analyze_image_with_gemini(image_file)
    if result:
        return result

    return _extract_mock(image_file)


def _extract_text_from_image(image_file) -> str:
    """Extract text from image using Azure Form Recognizer."""
    endpoint = settings.AZURE_FORM_RECOGNIZER_ENDPOINT
    key = settings.AZURE_FORM_RECOGNIZER_KEY

    if endpoint and key:
        try:
            from azure.ai.formrecognizer import DocumentAnalysisClient
            from azure.core.credentials import AzureKeyCredential

            client = DocumentAnalysisClient(
                endpoint=endpoint,
                credential=AzureKeyCredential(key),
            )

            image_file.seek(0)
            file_content = image_file.read()

            poller = client.begin_analyze_document("prebuilt-document", document=file_content)
            result = poller.result()

            # Extract all text
            full_text = ""
            for page in result.pages:
                for line in page.lines:
                    full_text += line.content + "\n"

            logger.info("Azure OCR extracted text successfully")
            return full_text

        except Exception as e:
            logger.error(f"Azure OCR failed: {e}")
            return None
    else:
        return None


def _parse_with_gemini(raw_text: str) -> dict:
    """Use Gemini to intelligently parse prescription text."""
    gemini_key = settings.GEMINI_API_KEY

    if not gemini_key:
        logger.warning("No Gemini API key, using simple parser")
        return _simple_parse(raw_text)

    try:
        import requests

        prompt = f"""You are a medical prescription parser. 
Extract structured data from this prescription text.

Return ONLY valid JSON (no markdown, no explanation):
{{
  "medications": [
    {{"name": "medicine name", "dosage": "amount", "frequency": "how often"}}
  ],
  "doctor_name": "doctor's name or empty",
  "date": "prescription date or empty"
}}

Prescription text:
{raw_text}

JSON:"""

        response = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_key}",
            headers={"Content-Type": "application/json"},
            json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.1, "maxOutputTokens": 65536}},
            timeout=30,
        )

        result = response.json()

        if "candidates" in result:
            text = result["candidates"][0]["content"]["parts"][0]["text"]
            # Clean up markdown formatting if any
            text = text.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]

            parsed = json.loads(text.strip())

            return {
                "medications": parsed.get("medications", []),
                "doctor_name": parsed.get("doctor_name", ""),
                "date": parsed.get("date", ""),
                "raw_text": raw_text,
            }

    except Exception as e:
        logger.error(f"Gemini parsing failed: {e}")

    # Fallback to simple parser
    return _simple_parse(raw_text)


def _simple_parse(text: str) -> dict:
    """Simple regex-based parser (fallback)."""
    import re

    medications = []
    lines = text.strip().split("\n")

    common_freqs = ["once daily", "twice daily", "thrice daily", "OD", "BD", "TDS", "QID", "once a day"]

    for line in lines:
        line = line.strip()
        if not line or len(line) < 3:
            continue

        # Look for dosage patterns
        dosage_match = re.search(r"(\d+\s*(?:mg|ml|mcg|tab|cap|tablet|capsule|g))", line, re.IGNORECASE)
        if dosage_match:
            name = line[: dosage_match.start()].strip().rstrip("-(").strip()
            dosage = dosage_match.group(1)

            freq = ""
            for f in common_freqs:
                if f.lower() in line.lower():
                    freq = f
                    break

            if name:
                medications.append(
                    {
                        "name": name,
                        "dosage": dosage,
                        "frequency": freq,
                    }
                )

    return {
        "medications": medications,
        "doctor_name": "",
        "date": "",
        "raw_text": text,
    }


def _detect_mime_type(image_file) -> str:
    name = getattr(image_file, "name", "")
    mime, _ = mimetypes.guess_type(name)
    return mime if mime in ("image/png", "image/jpeg", "image/webp") else "image/jpeg"


def _analyze_image_with_gemini(image_file) -> dict | None:
    """Send image bytes directly to Gemini multimodal vision."""
    gemini_key = settings.GEMINI_API_KEY
    if not gemini_key:
        return None

    try:
        import requests

        image_file.seek(0)
        image_bytes = image_file.read()
        mime_type = _detect_mime_type(image_file)
        encoded = base64.b64encode(image_bytes).decode("utf-8")

        prompt = """You are a medical prescription parser.
Extract all medication details from this prescription image.

Return ONLY valid JSON (no markdown, no explanation):
{
  "medications": [
    {"name": "medicine name", "dosage": "amount", "frequency": "how often"}
  ],
  "doctor_name": "doctor's name or empty",
  "date": "prescription date or empty"
}

JSON:"""

        response = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_key}",
            headers={"Content-Type": "application/json"},
            json={
                "contents": [
                    {
                        "parts": [
                            {"inline_data": {"mime_type": mime_type, "data": encoded}},
                            {"text": prompt},
                        ]
                    }
                ],
                "generationConfig": {"temperature": 0.1, "maxOutputTokens": 65536},
            },
            timeout=30,
        )

        result = response.json()

        if "candidates" in result:
            text = result["candidates"][0]["content"]["parts"][0]["text"]
            text = text.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]

            try:
                parsed = json.loads(text.strip())
            except json.JSONDecodeError as e:
                logger.error(f"Gemini vision JSON parse failed: {e}")
                logger.error(f"Raw Gemini response text: {text[:500]}")
                return None

            data = {
                "medications": parsed.get("medications", []),
                "doctor_name": parsed.get("doctor_name", ""),
                "date": parsed.get("date", ""),
                "raw_text": "",
            }
            logger.info("Gemini vision parsed prescription from image")
            return data

    except Exception as e:
        logger.error(f"Gemini vision failed: {e}")

    return None


def _extract_mock(image_file) -> dict:
    """Return mock data for demo."""
    return {
        "medications": [
            {"name": "Amoxicillin", "dosage": "500mg", "frequency": "thrice_daily"},
            {"name": "Ibuprofen", "dosage": "200mg", "frequency": "twice_daily"},
            {"name": "Omeprazole", "dosage": "20mg", "frequency": "once_daily"},
        ],
        "doctor_name": "Dr. Sarah Johnson",
        "date": "2026-02-15",
    }
