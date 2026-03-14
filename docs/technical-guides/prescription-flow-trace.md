# Technical Guide: Prescription Flow Trace (Advanced)

This document provides a granular code-level trace of how MedAssist processes physical prescription images.

---

## Stage 1: Client-Side Preparation
**Files**: `frontend/src/components/shared/PrescriptionScanner.tsx`

1. **Selection**: User picks an image file (JPEG/PNG).
2. **Payload Construction**:
   ```javascript
   const formData = new FormData();
   formData.append("image", file);
   formData.append("patient_id", selectedPatientId);
   ```
3. **Execution**: Hits `/api/prescriptions/scan/` via the central Axios `api` instance.

---

## Stage 2: The Logic Controller
**Files**: `backend/prescriptions/views.py` -> `PrescriptionScanView`

1. **Serializer Validation**: `PrescriptionScanSerializer` ensures the patient exists and belongs to the caretaker.
2. **The Entry Point**: The view calls the service layer:
   ```python
   extracted_data = extract_prescription_data(image)
   ```
3. **Audit Trail**: After extraction, a record in the `Prescription` model is created to store the raw image and the resulting JSON.

---

## Stage 3: The AI Processing Pipeline
**Files**: `backend/prescriptions/services/ocr_service.py`

This is where the transformation from "Pixels" to "JSON" happens.

### Step A: Azure OCR Layer (`_extract_text_from_image`)
- **System**: Azure AI Document Intelligence (prebuilt-document model).
- **Process**:
    - The image is streamed to Azure.
    - Azure returns a "DocumentAnalysis" object containing pages, lines, and words.
    - The code iterates through `result.pages` and concatenates every `line.content` into a single `full_text` string.

### Step B: Gemini Intelligence Layer (`_parse_with_gemini`)
- **System**: Generative AI (Gemini-2.0-Flash).
- **The Prompt**: The `full_text` is injected into a strict prompt:
  > "Extract structured data... Return ONLY valid JSON: { medications: [...] }"
- **Validation**: The JSON is parsed, cleaned of markdown backticks, and structured into a dictionary.

---

## Stage 4: Verification & Commitment
**Files**: `frontend/src/app/(dashboard)/caretaker/scan/page.tsx`

1. **State Injection**: The extracted JSON is set into the `ocrResults` state.
2. **Manual Review**: The UI displays editable cards.
3. **The Final POST**: When "Save All" is clicked, it makes individual (or bulk) calls to `/api/medications/`.

---

## Stage 5: Schema Integration
**Files**: `backend/medications/serializers.py` -> `MedicationCreateUpdateSerializer`

1. **Storage**: The `Medication` model saves the validated fields.
2. **JSON Mapping**: The `timings` field (e.g., `["09:00", "21:00"]`) is stored as a JSON list, allowing the `adherence` module to generate schedule logs without needing a complex relationship table.

---
### Technical Summary for Student Presenters:
> "We use a multi-stage pipeline: **Azure** handles the visual-to-text conversion (OCR), while **Gemini** handles the linguistic-to-schema extraction (LLM), ensuring that medical jargon is correctly mapped to our database fields."
