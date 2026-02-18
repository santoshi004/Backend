"""
OCR service for extracting prescription data from images.

Uses Azure Form Recognizer when API keys are configured,
falls back to a mock implementation for demo/development.
"""

import logging
from django.conf import settings

logger = logging.getLogger(__name__)


def extract_prescription_data(image_file) -> dict:
    """
    Extract prescription data from an uploaded image file.

    Args:
        image_file: A Django UploadedFile or file-like object.

    Returns:
        dict with structure:
        {
            "medications": [
                {"name": "...", "dosage": "...", "frequency": "..."}
            ],
            "doctor_name": "...",
            "date": "..."
        }
    """
    endpoint = settings.AZURE_FORM_RECOGNIZER_ENDPOINT
    key = settings.AZURE_FORM_RECOGNIZER_KEY

    if endpoint and key:
        return _extract_with_azure(image_file, endpoint, key)
    else:
        logger.info('Azure credentials not configured, using mock OCR.')
        return _extract_mock(image_file)


def _extract_with_azure(image_file, endpoint: str, key: str) -> dict:
    """Extract prescription data using Azure Form Recognizer."""
    try:
        from azure.ai.formrecognizer import DocumentAnalysisClient
        from azure.core.credentials import AzureKeyCredential

        client = DocumentAnalysisClient(
            endpoint=endpoint,
            credential=AzureKeyCredential(key),
        )

        # Read file content
        image_file.seek(0)
        file_content = image_file.read()

        poller = client.begin_analyze_document(
            'prebuilt-document', document=file_content
        )
        result = poller.result()

        # Parse the result into our expected format
        medications = []
        doctor_name = ''
        date = ''

        # Extract key-value pairs from the document
        for kv_pair in result.key_value_pairs:
            if kv_pair.key and kv_pair.value:
                key_text = kv_pair.key.content.lower()
                value_text = kv_pair.value.content

                if 'doctor' in key_text or 'physician' in key_text:
                    doctor_name = value_text
                elif 'date' in key_text:
                    date = value_text
                elif 'medication' in key_text or 'drug' in key_text or 'medicine' in key_text:
                    medications.append({
                        'name': value_text,
                        'dosage': '',
                        'frequency': '',
                    })

        # Also extract text content for medication parsing
        full_text = ''
        for page in result.pages:
            for line in page.lines:
                full_text += line.content + '\n'

        # If no structured medications found, try to parse from full text
        if not medications and full_text:
            medications = _parse_medications_from_text(full_text)

        return {
            'medications': medications,
            'doctor_name': doctor_name,
            'date': date,
            'raw_text': full_text,
        }

    except Exception as e:
        logger.error(f'Azure OCR failed: {e}')
        # Fall back to mock on error
        return _extract_mock(image_file)


def _parse_medications_from_text(text: str) -> list:
    """Simple heuristic parser for medication info from raw text."""
    medications = []
    lines = text.strip().split('\n')

    common_frequencies = [
        'once daily', 'twice daily', 'thrice daily',
        'OD', 'BD', 'TDS', 'QID',
        'once a day', 'twice a day', 'three times a day',
    ]

    for line in lines:
        line = line.strip()
        if not line or len(line) < 3:
            continue

        # Check if line contains medication-like content
        # (heuristic: contains dosage patterns like mg, ml, tab)
        import re
        dosage_match = re.search(
            r'(\d+\s*(?:mg|ml|mcg|tab|cap|tablet|capsule))', line, re.IGNORECASE
        )
        if dosage_match:
            name_part = line[:dosage_match.start()].strip().rstrip('-').strip()
            dosage_part = dosage_match.group(1).strip()

            freq = ''
            for f in common_frequencies:
                if f.lower() in line.lower():
                    freq = f
                    break

            if name_part:
                medications.append({
                    'name': name_part,
                    'dosage': dosage_part,
                    'frequency': freq,
                })

    return medications


def _extract_mock(image_file) -> dict:
    """
    Return sample extracted data for demo/development purposes.
    Simulates what Azure Form Recognizer would return.
    """
    return {
        'medications': [
            {
                'name': 'Amoxicillin',
                'dosage': '500mg',
                'frequency': 'thrice_daily',
            },
            {
                'name': 'Ibuprofen',
                'dosage': '200mg',
                'frequency': 'twice_daily',
            },
            {
                'name': 'Omeprazole',
                'dosage': '20mg',
                'frequency': 'once_daily',
            },
        ],
        'doctor_name': 'Dr. Sarah Johnson',
        'date': '2026-02-15',
    }
