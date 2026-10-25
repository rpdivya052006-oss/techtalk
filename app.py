import io
import re
import requests
import streamlit as st
import pytesseract

from PIL import Image
from pypdf import PdfReader
from docx import Document


# =====================================================
# PAGE CONFIGURATION
# =====================================================

st.set_page_config(
    page_title="Tamil Learning Assistant",
    page_icon="📚",
    layout="wide"
)

st.title("📚 Ancient Tamil & Poem Learning Assistant")

st.markdown(
    """
    Understand difficult Tamil in simple modern Tamil.

    - 📝 Tamil text simplification
    - 📄 PDF and image text extraction
    - 🗂️ Word document support
    - 📜 Tamil poem learning
    - 📖 Student-friendly explanations
    """
)


# =====================================================
# SARVAM AI
# =====================================================

API_URL = "https://api.sarvam.ai/v1/chat/completions"
MODEL_NAME = "sarvam-105b"


def get_api_key():
    try:
        return st.secrets["SARVAM_API_KEY"]
    except Exception:
        return ""


def call_sarvam(prompt, max_tokens=3500):

    api_key = get_api_key()

    if not api_key:
        raise RuntimeError(
            "SARVAM_API_KEY is missing. Add it in "
            "Streamlit Cloud → Settings → Secrets."
        )

    headers = {
        "api-subscription-key": api_key,
        "Content-Type": "application/json"
    }

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are an expert Tamil language teacher. "
                    "Explain Tamil accurately in natural, simple "
                    "modern Tamil. Preserve the original meaning. "
                    "Do not invent poem lines or historical facts. "
                    "Use language students can understand."
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "reasoning_effort": None,
        "max_tokens": max_tokens,
        "temperature": 0.2
    }

    try:
        response = requests.post(
            API_URL,
            headers=headers,
            json=payload,
            timeout=120
        )

    except requests.exceptions.Timeout:
        raise RuntimeError(
            "Sarvam took too long to respond. Please try again."
        )

    except requests.exceptions.RequestException as error:
        raise RuntimeError(
            f"Could not connect to Sarvam AI: {error}"
        )

    if not response.ok:
        try:
            data = response.json()
            error_data = data.get("error", {})

            if isinstance(error_data, dict):
                error_message = error_data.get("message")
            else:
                error_message = str(error_data)

            error_message = (
                error_message
                or data.get("message")
                or str(data)
            )

        except Exception:
            error_message = response.text[:500]

        raise RuntimeError(
            f"Sarvam API error ({response.status_code}): "
            f"{error_message}"
        )

    try:
        data = response.json()
    except ValueError:
        raise RuntimeError("Sarvam returned an invalid response.")

    choices = data.get("choices") or []

    if not choices:
        raise RuntimeError(
            "Sarvam did not return an answer. Please try again."
        )

    choice = choices[0] or {}
    message = choice.get("message") or {}
    content = message.get("content")

    if isinstance(content, str):
        result = content.strip()

    elif isinstance(content, list):
        result = "\n".join(
            str(part.get("text", ""))
            for part in content
            if isinstance(part, dict) and part.get("text")
        ).strip()

    else:
        result = ""

    if not result:
        raise RuntimeError(
            "Sarvam returned no visible text. Please try again."
        )

    return result


# =====================================================
# LONG TEXT PROCESSING
# =====================================================

def split_into_chunks(text, max_chars=1800):

    text = text.strip()

    if not text:
        return []

    chunks = []
    current = ""

    paragraphs = re.split(r"\n+", text)

    for paragraph in paragraphs:

        paragraph = paragraph.strip()

        if not paragraph:
            continue

        while len(paragraph) > max_chars:

            if current:
                chunks.append(current.strip())
                current = ""

            cut = paragraph.rfind(" ", 0, max_chars)

            if cut < max_chars // 2:
                cut = max_chars

            chunks.append(paragraph[:cut].strip())
            paragraph = paragraph[cut:].strip()

        if not paragraph:
            continue

        if len(current) + len(paragraph) + 1 <= max_chars:
            current = f"{current}\n{paragraph}".strip()

        else:
            if current:
                chunks.append(current.strip())

            current = paragraph

    if current:
        chunks.append(current.strip())

    return chunks


def simplify_long_text(text):

    chunks = split_into_chunks(text)

    if not chunks:
        raise RuntimeError("Please provide some Tamil text.")

    results = []

    progress = st.progress(0)
    status = st.empty()

    for index, chunk in enumerate(chunks, start=1):

        status.write(
            f"Simplifying part {index} of {len(chunks)}..."
        )

        prompt = f"""
Rewrite the following Tamil passage in simple, natural,
modern Tamil that school students can understand.

Rules:
1. Preserve the original meaning.
2. Write in Tamil script only.
3. Do not use Tanglish.
4. Do not translate into English.
5. Do not invent facts.
6. Explain difficult or old-fashioned expressions clearly.
7. Do not shorten unnecessarily.
8. Return only the simplified Tamil text.

Original Tamil passage:

{chunk}
"""

        results.append(
            call_sarvam(prompt, max_tokens=3500)
        )

        progress.progress(index / len(chunks))

    status.success("Tamil simplification completed!")

    return "\n\n".join(results)


# =====================================================
# FILE TEXT EXTRACTION
# =====================================================

def extract_text_from_image(uploaded_file):

    image = Image.open(
        io.BytesIO(uploaded_file.getvalue())
    ).convert("RGB")

    try:
        text = pytesseract.image_to_string(
            image,
            lang="tam+eng"
        )

    except Exception as error:
        raise RuntimeError(
            "Image OCR failed. Check packages.txt and make "
            "sure Tamil Tesseract support is installed. "
            f"Details: {error}"
        )

    if not text.strip():
        raise RuntimeError(
            "No text detected. Try a clearer image."
        )

    return text.strip()


def extract_text_from_pdf(uploaded_file):

    try:
        reader = PdfReader(
            io.BytesIO(uploaded_file.getvalue())
        )

        pages = [
            page.extract_text() or ""
            for page in reader.pages
        ]

        text = "\n\n".join(pages).strip()

    except Exception as error:
        raise RuntimeError(
            f"Could not read the PDF: {error}"
        )

    if not text:
        raise RuntimeError(
            "No selectable text was found in this PDF. "
            "It may be a scanned PDF. Upload the page as "
            "a JPG or PNG image instead."
        )

    return text


def extract_text_from_word(uploaded_file):

    try:
        document = Document(
            io.BytesIO(uploaded_file.getvalue())
        )

        paragraphs = [
            paragraph.text
            for paragraph in document.paragraphs
            if paragraph.text.strip()
        ]

        # Also extract text from tables in the document.
        for table in document.tables:
            for row in table.rows:
                row_text = " | ".join(
                    cell.text.strip()
                    for cell in row.cells
                    if cell.text.strip()
                )

                if row_text:
                    paragraphs.append(row_text)

        text = "\n".join(paragraphs).strip()

    except Exception as error:
        raise RuntimeError(
            f"Could not read the Word document: {error}"
        )

    if not text:
        raise RuntimeError(
            "No text was found in this Word document."
        )

    return text


def extract_uploaded_file(uploaded_file):

    name = uploaded_file.name.lower()

    if name.endswith(".pdf"):
        return extract_text_from_pdf(uploaded_file)

    if name.endswith(".docx"):
        return extract_text_from_word(uploaded_file)

    if name.endswith((".jpg", ".jpeg", ".png")):
        return extract_text_from_image(uploaded_file)

    raise RuntimeError("This file type is not supported.")


# =====================================================
# MAIN TABS
# =====================================================

text_tab, poem_tab = st.tabs([
    "📝 Tamil Text Simplifier",
    "📜 Tamil Poem Learning"
])


# =====================================================
# TAB 1: TEXT SIMPLIFIER
# =====================================================

with text_tab:

    st.header("📝 Tamil Text Simplifier")

    st.write(
        "Enter Tamil text or upload a PDF or image."
    )

    input_method = st.radio(
        "Choose input method:",
        ["Type or paste text", "Upload PDF or image"],
        horizontal=True,
        key="text_input_method"
    )

    original_text = ""

    if input_method == "Type or paste text":

        original_text = st.text_area(
            "Enter Tamil text:",
            height=250,
            placeholder="இங்கே தமிழ் உரையை உள்ளிடவும்...",
            key="manual_tamil_text"
        )

    else:

        uploaded_file = st.file_uploader(
            "Upload PDF, JPG, JPEG, or PNG",
            type=["pdf", "jpg", "jpeg", "png"],
            key="text_file_upload"
        )

        if uploaded_file is not None:

            try:
                original_text = extract_uploaded_file(
                    uploaded_file
                )

                st.success("Text extracted successfully!")

                st.text_area(
                    "Extracted text:",
                    value=original_text,
                    height=250,
                    key="extracted_text_preview"
                )

            except Exception as error:
                st.error(str(error))

    if st.button(
        "✨ Simplify Tamil Text",
        type="primary",
        key="simplify_text_button"
    ):

        if not original_text.strip():

            st.warning("Please enter text or upload a file.")

        else:

            try:
                with st.spinner(
                    "Converting into simple modern Tamil..."
                ):
                    simplified = simplify_long_text(original_text)

                left, right = st.columns(2)

                with left:
                    st.subheader("Original Tamil")
                    st.text_area(
                        "Original text",
                        value=original_text,
                        height=400,
                        key="original_result"
                    )

                with right:
                    st.subheader("Simple Modern Tamil")
                    st.text_area(
                        "Simplified text",
                        value=simplified,
                        height=400,
                        key="simplified_result"
                    )

            except Exception as error:
                st.error(str(error))


# =====================================================
# TAB 2: TAMIL POEM LEARNING
# =====================================================

with poem_tab:

    st.header("📜 Tamil Poem Learning")

    st.write(
        "Type a poem or upload its PDF, Word document, "
        "or image. The app will explain it for students."
    )

    poem_title = st.text_input(
        "Poem title (optional):",
        placeholder="Enter poem title",
        key="poem_title"
    )

    poem_author = st.text_input(
        "Poet name (optional):",
        placeholder="Enter poet name",
        key="poem_author"
    )

    poem_input_method = st.radio(
        "Choose how to provide the poem:",
        ["Type or paste poem", "Upload poem file"],
        horizontal=True,
        key="poem_input_method"
    )

    poem_text = ""

    if poem_input_method == "Type or paste poem":

        poem_text = st.text_area(
            "Enter your Tamil poem:",
            height=250,
            placeholder="இங்கே தமிழ்ப் பாடலை உள்ளிடவும்...",
            key="manual_poem_text"
        )

    else:

        poem_file = st.file_uploader(
            "Upload poem file",
            type=["pdf", "docx", "jpg", "jpeg", "png"],
            help=(
                "Supported formats: PDF, DOCX, JPG, JPEG, PNG. "
                "Scanned PDFs are not supported directly; "
                "upload their pages as images."
            ),
            key="poem_file_upload"
        )

        if poem_file is not None:

            try:
                poem_text = extract_uploaded_file(poem_file)

                st.success("Poem text extracted successfully!")

                st.markdown("#### Check the extracted poem")

                # Allow correction of OCR or extraction mistakes.
                poem_text = st.text_area(
                    "Review and correct the poem if necessary:",
                    value=poem_text,
                    height=250,
                    key="reviewed_poem_text"
                )

            except Exception as error:
                st.error(str(error))

    if st.button(
        "📚 Explain Poem in Simple Tamil",
        type="primary",
        key="explain_poem_button"
    ):

        if not poem_text.strip():

            st.warning(
                "Please enter a poem or upload a poem file."
            )

        else:

            try:

                prompt = f"""
You are a Tamil literature teacher helping school students.

Explain the supplied poem in simple, natural modern Tamil.

Title: {poem_title or "Not provided"}
Poet: {poem_author or "Not provided"}

ORIGINAL POEM:
{poem_text}

Use these headings in your response:

### 1. எளிய நவீன தமிழ்
Rewrite the poem's meaning in easy modern Tamil.
Preserve its original meaning. Do not invent poem lines.

### 2. பாடலின் மொத்தப் பொருள்
Explain the overall meaning and what the poet wants
readers to understand.

### 3. கடினமான சொற்களின் பொருள்
List important difficult words actually present in
the supplied poem and explain them in simple Tamil.
Use bullet points.

### 4. மாணவர்கள் கற்றுக்கொள்ள வேண்டியது
Give 2 to 4 points about the lesson or message.

### 5. சிறிய சுருக்கம்
Give a short, easy-to-remember summary.

Important rules:
- Write the answer in Tamil script.
- Do not use Tanglish.
- Do not translate into English.
- Do not invent missing poem lines or historical facts.
- If the poem is incomplete or ambiguous, say so.
- Keep the explanation suitable for students.
"""

                with st.spinner(
                    "Preparing the poem explanation..."
                ):
                    explanation = call_sarvam(
                        prompt,
                        max_tokens=3500
                    )

                st.success("Poem explanation is ready!")

                st.markdown("## 📜 Original Poem")

                if poem_title.strip():
                    st.markdown(f"**{poem_title}**")

                if poem_author.strip():
                    st.caption(f"Poet: {poem_author}")

                st.text_area(
                    "Final poem text",
                    value=poem_text,
                    height=200,
                    key="final_poem_display"
                )

                st.markdown("## 🎓 Student-Friendly Explanation")

                st.markdown(explanation)

            except Exception as error:
                st.error(str(error))


# =====================================================
# FOOTER
# =====================================================

st.markdown("---")

st.caption(
    "Tamil Learning Assistant | Powered by Sarvam AI | "
    "For educational use. Verify poem text and interpretations "
    "with a trusted textbook or Tamil literature source."
)












