
import io
import re
import requests
import streamlit as st
import pytesseract

from PIL import Image
from pypdf import PdfReader


# =====================================================
# PAGE CONFIGURATION
# =====================================================

st.set_page_config(
    page_title="Tamil Learning Assistant",
    page_icon="📚",
    layout="wide"
)


# =====================================================
# APP TITLE
# =====================================================

st.title("📚 Ancient Tamil & Poem Learning Assistant")

st.markdown(
    """
    Understand difficult Tamil in simple modern Tamil.

    - 📝 Tamil text simplification
    - 📄 PDF and image text extraction
    - 📜 Tamil poem simplification
    - 📖 Easy explanations and difficult-word meanings
    """
)


# =====================================================
# SARVAM AI CONFIGURATION
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
            "SARVAM_API_KEY is missing. "
            "Add it in Streamlit Cloud → Settings → Secrets."
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
                    "Explain Tamil text accurately in clear, natural "
                    "modern Tamil. Preserve the original meaning. "
                    "Do not invent poem lines or facts. "
                    "Use simple Tamil that students can understand."
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
        raise RuntimeError(
            "Sarvam returned an invalid response."
        )

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
        text_parts = []

        for part in content:
            if isinstance(part, dict) and part.get("text"):
                text_parts.append(str(part["text"]))

        result = "\n".join(text_parts).strip()

    else:
        result = ""

    if not result:
        finish_reason = choice.get("finish_reason", "unknown")

        raise RuntimeError(
            "Sarvam returned no visible text. "
            f"Finish reason: {finish_reason}. Please try again."
        )

    return result


# =====================================================
# SPLIT LONG TEXT INTO SMALLER PARTS
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

            cut_position = paragraph.rfind(" ", 0, max_chars)

            if cut_position < max_chars // 2:
                cut_position = max_chars

            chunks.append(
                paragraph[:cut_position].strip()
            )

            paragraph = paragraph[cut_position:].strip()

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


# =====================================================
# SIMPLIFY LONG TAMIL TEXT
# =====================================================

def simplify_long_text(text):

    chunks = split_into_chunks(text)

    if not chunks:
        raise RuntimeError(
            "Please enter or upload some Tamil text."
        )

    simplified_chunks = []

    progress = st.progress(0)
    status = st.empty()

    for index, chunk in enumerate(chunks, start=1):

        status.write(
            f"Processing part {index} of {len(chunks)}..."
        )

        prompt = f"""
Convert the following Tamil passage into simple, natural,
modern Tamil that school students can understand.

Instructions:
1. Preserve the original meaning and important information.
2. Write the answer in Tamil script.
3. Do not use Tanglish or Roman letters to write Tamil.
4. Do not translate the answer into English.
5. Do not shorten the passage unnecessarily.
6. Do not invent facts or add unrelated information.
7. Explain difficult and old-fashioned expressions using
   appropriate modern Tamil.
8. Return only the simplified Tamil passage.

Original Tamil passage:

{chunk}
"""

        answer = call_sarvam(
            prompt,
            max_tokens=3500
        )

        simplified_chunks.append(answer)

        progress.progress(index / len(chunks))

    status.success("Tamil simplification completed!")

    return "\n\n".join(simplified_chunks)


# =====================================================
# EXTRACT TEXT FROM IMAGES
# =====================================================

def extract_text_from_image(uploaded_file):

    image_bytes = uploaded_file.getvalue()

    image = Image.open(
        io.BytesIO(image_bytes)
    ).convert("RGB")

    try:
        extracted_text = pytesseract.image_to_string(
            image,
            lang="tam+eng"
        )

    except Exception as error:
        raise RuntimeError(
            "Tamil OCR failed. Check packages.txt and ensure "
            "Tamil Tesseract language support is installed. "
            f"Details: {error}"
        )

    if not extracted_text.strip():
        raise RuntimeError(
            "No text was detected. Please upload a clearer image."
        )

    return extracted_text.strip()


# =====================================================
# EXTRACT TEXT FROM PDF
# =====================================================

def extract_text_from_pdf(uploaded_file):

    pdf_bytes = io.BytesIO(
        uploaded_file.getvalue()
    )

    try:
        reader = PdfReader(pdf_bytes)

        page_texts = []

        for page in reader.pages:
            page_texts.append(
                page.extract_text() or ""
            )

        extracted_text = "\n\n".join(
            page_texts
        ).strip()

    except Exception as error:
        raise RuntimeError(
            f"Could not read the PDF: {error}"
        )

    if not extracted_text:
        raise RuntimeError(
            "No selectable text was found in this PDF. "
            "If it is a scanned PDF, save its page as an image "
            "and upload the JPG or PNG instead."
        )

    return extracted_text


# =====================================================
# NAVIGATION TABS
# =====================================================

text_tab, poem_tab = st.tabs([
    "📝 Tamil Text Simplifier",
    "📜 Tamil Poem Learning"
])


# =====================================================
# TAB 1: TAMIL TEXT SIMPLIFIER
# =====================================================

with text_tab:

    st.header(
        "📝 Convert Difficult Tamil into Simple Tamil"
    )

    st.write(
        "Type or paste Tamil text, or upload a PDF or image. "
        "The app extracts the text and simplifies it for students."
    )

    input_method = st.radio(
        "Choose your input method:",
        [
            "Type or paste text",
            "Upload PDF or image"
        ],
        horizontal=True,
        key="text_input_method"
    )

    original_text = ""

    if input_method == "Type or paste text":

        original_text = st.text_area(
            "Enter your Tamil text:",
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

            file_name = uploaded_file.name.lower()

            try:

                if file_name.endswith(".pdf"):

                    original_text = extract_text_from_pdf(
                        uploaded_file
                    )

                else:

                    original_text = extract_text_from_image(
                        uploaded_file
                    )

                st.success(
                    "Text extracted successfully!"
                )

                st.text_area(
                    "Extracted original text:",
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

            st.warning(
                "Please enter Tamil text or upload a file."
            )

        else:

            try:

                with st.spinner(
                    "Converting into simple modern Tamil..."
                ):

                    simplified_text = simplify_long_text(
                        original_text
                    )

                st.subheader(
                    "📖 Original and Simplified Tamil"
                )

                original_column, simplified_column = st.columns(2)

                with original_column:

                    st.markdown("#### Original Tamil")

                    st.text_area(
                        "Original text",
                        value=original_text,
                        height=400,
                        key="original_result"
                    )

                with simplified_column:

                    st.markdown("#### Simple Modern Tamil")

                    st.text_area(
                        "Simplified text",
                        value=simplified_text,
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
        "Paste any Tamil poem to understand its meaning "
        "in simple modern Tamil."
    )

    poem_title = st.text_input(
        "Poem title (optional):",
        placeholder="Enter the poem title",
        key="custom_poem_title"
    )

    poem_author = st.text_input(
        "Poet name (optional):",
        placeholder="Enter the poet's name",
        key="custom_poem_author"
    )

    poem_text = st.text_area(
        "Paste your Tamil poem:",
        height=250,
        placeholder=(
            "இங்கே முழுத் தமிழ்ப் பாடலையும் உள்ளிடவும்..."
        ),
        key="custom_poem_text"
    )

    st.caption(
        "Tip: Paste the complete poem for a more useful explanation."
    )

    if st.button(
        "📚 Explain Poem in Simple Tamil",
        type="primary",
        key="explain_poem_button"
    ):

        if not poem_text.strip():

            st.warning(
                "Please paste a Tamil poem first."
            )

        else:

            try:

                poem_prompt = f"""
You are a Tamil literature teacher helping school students.

Explain the following poem in simple, natural modern Tamil.

Poem title: {poem_title or "Not provided"}
Poet: {poem_author or "Not provided"}

ORIGINAL POEM:
{poem_text}

Give the answer under these headings:

### 1. எளிய நவீன தமிழ்

Rewrite the poem's meaning in simple modern Tamil.
Preserve the original ideas and important details.
Do not invent new poem lines.

### 2. பாடலின் மொத்தப் பொருள்

Explain the central meaning of the poem in easy Tamil.
Explain what the poet wants readers to understand.

### 3. கடினமான சொற்களின் பொருள்

List important difficult words that actually appear
in the supplied poem.

Explain each word in simple Tamil using bullet points.
Use the meaning that best fits the poem's context.

### 4. மாணவர்கள் கற்றுக்கொள்ள வேண்டியது

Give 2 to 4 short points about the lesson or message
students can learn from this poem.

### 5. சிறிய சுருக்கம்

Give a short, easy-to-remember summary in Tamil.

IMPORTANT RULES:
- Write the entire answer in Tamil script.
- Do not use Tanglish.
- Do not translate the answer into English.
- Preserve the poem's intended meaning.
- Do not invent missing poem lines or historical facts.
- If the poem is incomplete or its meaning is uncertain,
  clearly mention that limitation.
- Keep the explanation suitable for students.
"""

                with st.spinner(
                    "Preparing the poem explanation..."
                ):

                    poem_explanation = call_sarvam(
                        poem_prompt,
                        max_tokens=3500
                    )

                st.success(
                    "Poem explanation is ready!"
                )

                st.markdown("## 📜 Original Poem")

                if poem_title.strip():
                    st.markdown(f"**{poem_title}**")

                if poem_author.strip():
                    st.caption(f"Poet: {poem_author}")

                st.text_area(
                    "Original poem text",
                    value=poem_text,
                    height=200,
                    key="poem_original_result"
                )

                st.markdown(
                    "## 🎓 Student-Friendly Explanation"
                )

                st.markdown(poem_explanation)

            except Exception as error:
                st.error(str(error))


# =====================================================
# FOOTER
# =====================================================

st.markdown("---")

st.caption(
    "Tamil Learning Assistant | Powered by Sarvam AI | "
    "For educational use. Check literary interpretations "
    "against your textbook or a trusted Tamil literature source."
)








