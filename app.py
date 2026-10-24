
import requests
import streamlit as st
import pytesseract

from PIL import Image
from pypdf import PdfReader


# ==================================================
# 1. PAGE CONFIGURATION
# ==================================================
st.set_page_config(
    page_title="Ancient Tamil to Simple Tamil",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("📚 Ancient Tamil to Simple Modern Tamil")

st.markdown(
    """
    Convert difficult Tamil literature, classical Tamil, book passages,
    and newspaper text into **simple, natural modern Tamil**.

    **Features:** Tamil text input • PDF upload • Image OCR •
    Original vs Simple Tamil comparison
    """
)

st.divider()


# ==================================================
# 2. SARVAM AI API
# ==================================================
def simplify_chunk(text):
    api_key = st.secrets.get("SARVAM_API_KEY", "")

    if not api_key:
        raise RuntimeError(
            "SARVAM_API_KEY is missing. Add your API key "
            "under Streamlit Cloud → Settings → Secrets."
        )

    url = "https://api.sarvam.ai/v1/chat/completions"

    headers = {
        "api-subscription-key": api_key,
        "Content-Type": "application/json"
    }

    payload = {
        "model": "sarvam-105b",
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are an expert Tamil language simplifier. "
                    "Your task is to rewrite difficult, classical, or "
                    "formal Tamil into simple, natural modern Tamil. "
                    "Rewrite the COMPLETE passage. Do not summarize it. "
                    "Do not omit sentences, facts, events, names, or "
                    "important details. Explain difficult Tamil words "
                    "using simpler Tamil expressions when necessary. "
                    "Preserve the original meaning and tone. "
                    "Use Tamil script, not Tanglish. "
                    "Do not translate the passage into English. "
                    "Return only the simplified Tamil passage."
                )
            },
            {
                "role": "user",
                "content": (
                    "Rewrite every sentence in the following passage "
                    "in simple modern Tamil. Keep every important detail. "
                    "Do not stop after the first sentence.\n\n"
                    + text
                )
            }
        ],
        "temperature": 0.2,
        "max_tokens": 4000,
        "reasoning_effort": None
    }

    try:
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=180
        )

    except requests.RequestException as error:
        raise RuntimeError(
            f"Could not connect to Sarvam AI: {error}"
        ) from error

    if not response.ok:
        raise RuntimeError(
            f"Sarvam API returned HTTP {response.status_code}.\n"
            f"Details: {response.text[:1000]}"
        )

    try:
        data = response.json()

    except ValueError as error:
        raise RuntimeError(
            "Sarvam returned an invalid JSON response."
        ) from error

    choices = data.get("choices") or []

    if not choices:
        raise RuntimeError(
            "Sarvam returned no choices.\n"
            f"Response: {str(data)[:1500]}"
        )

    choice = choices[0] or {}
    message = choice.get("message") or {}
    content = message.get("content")

    # Handle normal string responses.
    if isinstance(content, str):
        result = content.strip()

    # Handle responses containing multiple text blocks.
    elif isinstance(content, list):
        parts = []

        for item in content:
            if isinstance(item, str):
                parts.append(item)

            elif isinstance(item, dict):
                item_text = item.get("text")

                if isinstance(item_text, str):
                    parts.append(item_text)

        result = "\n".join(parts).strip()

    else:
        result = ""

    # Handle missing or empty output safely.
    if not result:
        finish_reason = choice.get("finish_reason")
        reasoning = message.get("reasoning_content")

        details = (
            f"Finish reason: {finish_reason}. "
            f"Reasoning content present: {bool(reasoning)}."
        )

        raise RuntimeError(
            "Sarvam did not return visible text. "
            + details
            + " Please check the API response and try again."
        )

    return result


# ==================================================
# 3. SPLIT LONG TEXT INTO SMALLER PARTS
# ==================================================
def split_text(text, max_chars=1800):
    """
    Split a long passage at word boundaries.
    This helps prevent individual API responses from becoming too long.
    """

    words = text.split()
    chunks = []
    current_words = []
    current_length = 0

    for word in words:
        extra_length = len(word) + 1

        if current_words and current_length + extra_length > max_chars:
            chunks.append(" ".join(current_words))
            current_words = [word]
            current_length = len(word)

        else:
            current_words.append(word)
            current_length += extra_length

    if current_words:
        chunks.append(" ".join(current_words))

    return chunks


# ==================================================
# 4. SIMPLIFY THE COMPLETE PASSAGE
# ==================================================
def simplify_tamil(text):
    chunks = split_text(text)

    if not chunks:
        raise ValueError("Please enter Tamil text.")

    simplified_parts = []

    progress_bar = st.progress(0)
    status = st.empty()

    try:
        for index, chunk in enumerate(chunks):
            status.info(
                f"Processing part {index + 1} of {len(chunks)}..."
            )

            result = simplify_chunk(chunk)

            # Warn if the response is unusually short.
            if len(chunk) > 150 and len(result) < 40:
                raise RuntimeError(
                    f"Part {index + 1} produced a very short answer. "
                    "Please try this part again."
                )

            simplified_parts.append(result)

            progress_bar.progress(
                (index + 1) / len(chunks)
            )

    finally:
        progress_bar.empty()
        status.empty()

    return "\n\n".join(simplified_parts)


# ==================================================
# 5. IMAGE OCR
# ==================================================
def extract_text_from_image(image):
    try:
        extracted = pytesseract.image_to_string(
            image,
            lang="tam+eng"
        )

        return extracted.strip()

    except Exception as error:
        raise RuntimeError(
            "Tamil OCR failed. Check that packages.txt contains "
            "tesseract-ocr and tesseract-ocr-tam. "
            "Try uploading a clearer image."
        ) from error


# ==================================================
# 6. PDF TEXT EXTRACTION
# ==================================================
def extract_text_from_pdf(uploaded_file):
    try:
        reader = PdfReader(uploaded_file)
        pages = []

        for page_number, page in enumerate(reader.pages, start=1):
            page_text = page.extract_text() or ""

            if page_text.strip():
                pages.append(page_text.strip())

        return "\n\n".join(pages)

    except Exception as error:
        raise RuntimeError(
            f"Could not read the PDF: {error}"
        ) from error


# ==================================================
# 7. FILE UPLOAD SECTION
# ==================================================
st.header("1. Upload a PDF or image")

uploaded_file = st.file_uploader(
    "Select a file containing Tamil text",
    type=["pdf", "jpg", "jpeg", "png"],
    help="Supported files: PDF, JPG, JPEG and PNG."
)

if uploaded_file is not None:

    file_name = uploaded_file.name.lower()

    try:
        if file_name.endswith(".pdf"):

            with st.spinner("Reading PDF..."):
                extracted_text = extract_text_from_pdf(uploaded_file)

            if extracted_text:
                st.session_state["input_text"] = extracted_text

                st.success(
                    "PDF text extracted. You can review it below."
                )

            else:
                st.warning(
                    "No selectable text was found in this PDF. "
                    "If it is a scanned document, upload its pages "
                    "as JPG or PNG images instead."
                )

        else:
            image_file = Image.open(uploaded_file).convert("RGB")

            st.image(
                image_file,
                caption="Uploaded image",
                use_container_width=True
            )

            with st.spinner("Extracting Tamil text from image..."):
                extracted_text = extract_text_from_image(image_file)

            if extracted_text:
                st.session_state["input_text"] = extracted_text

                st.success(
                    "Image text extracted. Review it in the text box below."
                )

            else:
                st.warning(
                    "No text was detected. Try a clearer image "
                    "with larger, sharper Tamil letters."
                )

    except Exception as error:
        st.error(str(error))


st.divider()


# ==================================================
# 8. TEXT INPUT SECTION
# ==================================================
st.header("2. Enter or review Tamil text")

if "input_text" not in st.session_state:
    st.session_state["input_text"] = ""

input_text = st.text_area(
    "Your Tamil passage",
    key="input_text",
    height=260,
    placeholder=(
        "இங்கே பழந்தமிழ் அல்லது கடினமான தமிழ் உரையை உள்ளிடவும்..."
    ),
    help="You can paste text directly or edit the text extracted from a file."
)

st.caption(
    f"Characters entered: {len(input_text)}"
)


# ==================================================
# 9. CONVERSION BUTTON
# ==================================================
st.header("3. Convert to Simple Tamil")

convert_button = st.button(
    "✨ Convert to Simple Tamil",
    type="primary",
    use_container_width=False
)

if convert_button:

    if not input_text.strip():
        st.warning(
            "Please enter Tamil text or upload a readable file first."
        )

    else:
        try:
            with st.spinner(
                "Sarvam AI is rewriting your passage..."
            ):
                simplified_text = simplify_tamil(
                    input_text.strip()
                )

            st.session_state["original_text"] = input_text.strip()
            st.session_state["simple_text"] = simplified_text

            st.success(
                "Your Tamil passage has been converted!"
            )

        except Exception as error:
            st.error(
                f"Conversion failed: {error}"
            )


# ==================================================
# 10. ORIGINAL VS SIMPLE TAMIL
# ==================================================
original_text = st.session_state.get("original_text", "")
simple_text = st.session_state.get("simple_text", "")

if original_text and simple_text:

    st.divider()
    st.header("4. Original vs Simple Tamil")

    original_column, simple_column = st.columns(2)

    with original_column:
        st.subheader("📜 Original Tamil")

        st.text_area(
            "Original passage",
            value=original_text,
            height=450,
            disabled=True,
            key="original_display"
        )

    with simple_column:
        st.subheader("🌱 Simple Modern Tamil")

        st.text_area(
            "Simplified passage",
            value=simple_text,
            height=450,
            disabled=True,
            key="simple_display"
        )

    st.info(
        "Please review the simplified passage to ensure the original "
        "meaning and important information are preserved."
    )

    st.caption(
        f"Original: {len(original_text)} characters | "
        f"Simplified: {len(simple_text)} characters"
    )


# ==================================================
# 11. FOOTER
# ==================================================
st.divider()

st.caption(
    "Ancient Tamil to Simple Modern Tamil | Powered by Sarvam AI"
)




