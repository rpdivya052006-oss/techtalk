
import io
import re
import hashlib
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
    - 🎙️ Tamil voice-to-text
    - 📄 PDF and image text extraction
    - 🗂️ Word document support
    - 📜 Tamil poem learning
    - 🕘 History
    - 📖 Student-friendly explanations
    """
)


# =====================================================
# SESSION STATE
# =====================================================

defaults = {
    "latest_original_text": "",
    "latest_simplified_text": "",
    "history": [],
    "recognized_voice_text": "",
    "active_text_file_id": "",
    "extracted_text_preview": "",
    "active_poem_file_id": "",
    "reviewed_poem_text": "",
    "poem_explanation": "",
    "latest_poem_text": ""
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


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
# VOICE TO TEXT
# =====================================================

def convert_voice_to_text(audio_file):

    api_key = get_api_key()

    if not api_key:
        raise RuntimeError(
            "SARVAM_API_KEY is missing. Add it in "
            "Streamlit Cloud → Settings → Secrets."
        )

    headers = {
        "api-subscription-key": api_key
    }

    files = {
        "file": (
            "tamil_voice.wav",
            audio_file.getvalue(),
            "audio/wav"
        )
    }

    data = {
        "model": "saaras:v2.5",
        "language_code": "ta-IN"
    }

    try:
        response = requests.post(
            "https://api.sarvam.ai/speech-to-text",
            headers=headers,
            files=files,
            data=data,
            timeout=120
        )

    except requests.exceptions.RequestException as error:
        raise RuntimeError(
            f"Voice conversion failed: {error}"
        )

    if not response.ok:
        raise RuntimeError(
            f"Voice API error ({response.status_code}): "
            f"{response.text[:500]}"
        )

    result = response.json()
    transcript = result.get("transcript", "").strip()

    if not transcript:
        raise RuntimeError(
            "No speech was detected. Please record again."
        )

    return transcript


# =====================================================
# MAIN TABS
# =====================================================

text_tab, poem_tab, history_tab = st.tabs([
    "📝 Tamil Text Simplifier",
    "📜 Tamil Poem Learning",
    "🕘 History"
])


# =====================================================
# TAB 1: TEXT SIMPLIFIER
# =====================================================

with text_tab:

    st.header("📝 Tamil Text Simplifier")

    st.write(
        "Type Tamil text, speak, or upload a PDF, Word document, or image."
    )

    input_method = st.radio(
        "Choose input method:",
        [
            "Type or paste text",
            "Speak in Tamil",
            "Upload file or image"
        ],
        horizontal=True,
        key="text_input_method"
    )

    original_text = ""

    if input_method == "Type or paste text":

        # The widget keeps the current editable input.
        original_text = st.text_area(
            "Enter Tamil text:",
            height=250,
            placeholder="இங்கே தமிழ் உரையை உள்ளிடவும்...",
            key="manual_tamil_text"
        )

    elif input_method == "Speak in Tamil":

        audio_file = st.audio_input(
            "Record your Tamil speech",
            key="tamil_voice_input"
        )

        if audio_file is not None:

            audio_id = hashlib.md5(
                audio_file.getvalue()
            ).hexdigest()

            if st.session_state.get("voice_audio_id") != audio_id:

                try:
                    with st.spinner("Converting voice to text..."):
                        transcript = convert_voice_to_text(audio_file)

                    st.session_state["recognized_voice_text"] = transcript
                    st.session_state["voice_audio_id"] = audio_id

                except Exception as error:
                    st.error(str(error))

        original_text = st.text_area(
            "Recognized Tamil text (you can edit it):",
            height=250,
            key="recognized_voice_text"
        )

    else:

        uploaded_file = st.file_uploader(
            "Upload PDF, DOCX, JPG, JPEG, or PNG",
            type=["pdf", "docx", "jpg", "jpeg", "png"],
            key="text_file_upload"
        )

        if uploaded_file is not None:

            try:
                file_id = hashlib.md5(
                    uploaded_file.getvalue()
                ).hexdigest()

                # Re-extract when a different file is uploaded.
                if st.session_state.get("active_text_file_id") != file_id:

                    extracted = extract_uploaded_file(uploaded_file)

                    st.session_state["active_text_file_id"] = file_id
                    st.session_state["extracted_text_preview"] = extracted

                original_text = st.text_area(
                    "Extracted text (you can edit it):",
                    height=250,
                    key="extracted_text_preview"
                )

            except Exception as error:
                st.error(str(error))

        else:
            st.session_state["active_text_file_id"] = ""
            st.session_state["extracted_text_preview"] = ""

    if st.button(
        "✨ Simplify Tamil Text",
        type="primary",
        key="simplify_text_button"
    ):

        latest_text = original_text.strip()

        if not latest_text:
            st.warning("Please enter text or upload a file.")

        else:

            try:
                with st.spinner(
                    "Converting into simple modern Tamil..."
                ):
                    simplified = simplify_long_text(latest_text)

                # Replace old result with the latest result.
                st.session_state["latest_original_text"] = latest_text
                st.session_state["latest_simplified_text"] = simplified

                st.session_state["history"].insert(
                    0,
                    {
                        "original": latest_text,
                        "simplified": simplified
                    }
                )

                st.success("New text simplified successfully!")

            except Exception as error:
                st.error(str(error))

    if st.session_state["latest_simplified_text"]:

        left, right = st.columns(2)

        with left:
            st.subheader("Original Tamil")
            st.text_area(
                "Original text",
                value=st.session_state["latest_original_text"],
                height=400,
                key="latest_original_display"
            )

        with right:
            st.subheader("Simple Modern Tamil")
            st.text_area(
                "Simplified text",
                value=st.session_state["latest_simplified_text"],
                height=400,
                key="latest_simplified_display"
            )


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
                poem_file_id = hashlib.md5(
                    poem_file.getvalue()
                ).hexdigest()

                if st.session_state.get("active_poem_file_id") != poem_file_id:

                    extracted_poem = extract_uploaded_file(poem_file)

                    st.session_state["active_poem_file_id"] = poem_file_id
                    st.session_state["reviewed_poem_text"] = extracted_poem

                st.success("Poem text extracted successfully!")

                poem_text = st.text_area(
                    "Review and correct the poem if necessary:",
                    height=250,
                    key="reviewed_poem_text"
                )

            except Exception as error:
                st.error(str(error))

        else:
            st.session_state["active_poem_file_id"] = ""
            st.session_state["reviewed_poem_text"] = ""

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

                st.session_state["latest_poem_text"] = poem_text
                st.session_state["poem_explanation"] = explanation

                st.session_state["history"].insert(
                    0,
                    {
                        "original": f"Poem: {poem_title or 'Untitled'}\n{poem_text}",
                        "simplified": explanation
                    }
                )

                st.success("Poem explanation is ready!")

            except Exception as error:
                st.error(str(error))

    if st.session_state["poem_explanation"]:

        st.markdown("## 📜 Original Poem")

        if poem_title.strip():
            st.markdown(f"**{poem_title}**")

        if poem_author.strip():
            st.caption(f"Poet: {poem_author}")

        st.text_area(
            "Final poem text",
            value=st.session_state["latest_poem_text"],
            height=200,
            key="final_poem_display"
        )

        st.markdown("## 🎓 Student-Friendly Explanation")
        st.markdown(st.session_state["poem_explanation"])


# =====================================================
# TAB 3: HISTORY
# =====================================================

with history_tab:

    st.header("🕘 History")

    st.write(
        "Your recent text simplifications and poem explanations "
        "are stored during this app session."
    )

    if st.button("🗑️ Clear History", key="clear_history_button"):

        st.session_state["history"] = []
        st.success("History cleared.")

    if not st.session_state["history"]:

        st.info("No history yet. Simplify a text or explain a poem first.")

    else:

        for index, item in enumerate(st.session_state["history"]):

            with st.expander(
                f"History {index + 1}"
            ):

                st.markdown("**Original Text / Poem**")
                st.text(item["original"])

                st.markdown("**Simplified Text / Explanation**")
                st.text(item["simplified"])


# =====================================================
# FOOTER
# =====================================================

st.markdown("---")

st.caption(
    "Tamil Learning Assistant | Powered by Sarvam AI | "
    "For educational use. Verify poem text and interpretations "
    "with a trusted textbook or Tamil literature source."
)












