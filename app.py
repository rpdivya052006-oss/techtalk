
import io
import requests
import streamlit as st
import pytesseract

from PIL import Image
from pypdf import PdfReader


# ---------------- PAGE SETTINGS ----------------
st.set_page_config(
    page_title="Ancient Tamil to Simple Tamil",
    page_icon="📚",
    layout="wide"
)

st.title("📚 Ancient Tamil to Simple Modern Tamil")
st.write(
    "Difficult Tamil text-ai simple, natural modern Tamil-aaga maatralaam."
)


# ---------------- SARVAM API ----------------
def simplify_chunk(text):
    api_key = st.secrets.get("SARVAM_API_KEY", "")

    if not api_key:
        raise ValueError(
            "SARVAM_API_KEY missing. Streamlit Secrets-la API key add pannunga."
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
                    "Rewrite the COMPLETE input passage in simple, "
                    "natural, easy-to-understand modern Tamil. "
                    "Do not summarize. Do not omit sentences, events, "
                    "names, facts, or important details. Explain difficult "
                    "classical Tamil words in simple Tamil when needed. "
                    "Use Tamil script, not Tanglish. Do not translate into "
                    "English. Return only the rewritten Tamil passage."
                )
            },
            {
                "role": "user",
                "content": (
                    "Rewrite every sentence in this passage. Preserve "
                    "the full meaning and all details:\n\n" + text
                )
            }
        ],
        "temperature": 0.2,
        "max_tokens": 4000
    }

    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=120
    )

    if not response.ok:
        raise RuntimeError(
            f"Sarvam API error ({response.status_code}): "
            f"{response.text[:700]}"
        )

    data = response.json()

    try:
        result = data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError):
        raise RuntimeError(
            "Sarvam response format unexpected. Please check the API response."
        )

    if not result:
        raise RuntimeError("Sarvam returned an empty response.")

    return result


# ---------------- PROCESS LONG TEXT ----------------
def split_text(text, max_chars=1800):
    """
    Split long text into smaller chunks so that long passages
    are less likely to be cut off in one API response.
    """
    words = text.split()
    chunks = []
    current = ""

    for word in words:
        if len(current) + len(word) + 1 > max_chars and current:
            chunks.append(current)
            current = word
        else:
            current = f"{current} {word}".strip()

    if current:
        chunks.append(current)

    return chunks


def simplify_tamil(text):
    chunks = split_text(text)
    simplified_chunks = []

    progress = st.progress(0)
    status = st.empty()

    for index, chunk in enumerate(chunks):
        status.write(
            f"Converting part {index + 1} of {len(chunks)}..."
        )

        result = simplify_chunk(chunk)

        # Warn if the returned text is unusually short.
        # This does not automatically prove the answer is incomplete.
        if len(chunk) > 150 and len(result) < 40:
            raise RuntimeError(
                "Sarvam returned a very short answer for a long passage. "
                "Please try again or split the passage into smaller parts."
            )

        simplified_chunks.append(result)
        progress.progress((index + 1) / len(chunks))

    status.empty()
    progress.empty()

    return "\n\n".join(simplified_chunks)


# ---------------- IMAGE OCR ----------------
def extract_from_image(image):
    try:
        return pytesseract.image_to_string(
            image,
            lang="tam+eng"
        ).strip()
    except Exception as error:
        raise RuntimeError(
            "Image OCR failed. Check packages.txt and try a clearer image."
        ) from error


# ---------------- PDF TEXT EXTRACTION ----------------
def extract_from_pdf(uploaded_file):
    reader = PdfReader(uploaded_file)
    pages = []

    for page in reader.pages:
        pages.append(page.extract_text() or "")

    return "\n\n".join(pages).strip()


# ---------------- UPLOAD SECTION ----------------
st.subheader("1. Upload a PDF or image")

uploaded_file = st.file_uploader(
    "Choose a file containing Tamil text",
    type=["pdf", "jpg", "jpeg", "png"]
)

extracted_text = ""

if uploaded_file is not None:
    filename = uploaded_file.name.lower()

    try:
        if filename.endswith(".pdf"):
            extracted_text = extract_from_pdf(uploaded_file)

            if not extracted_text:
                st.warning(
                    "This PDF may contain scanned images instead of selectable "
                    "text. Please upload the page as a JPG or PNG image."
                )

        else:
            image_file = Image.open(uploaded_file).convert("RGB")

            st.image(
                image_file,
                caption="Uploaded image",
                use_container_width=True
            )

            with st.spinner("Extracting Tamil text from image..."):
                extracted_text = extract_from_image(image_file)

        if extracted_text:
            st.success("Text extracted successfully.")

    except Exception as error:
        st.error(f"Could not read the file: {error}")


# ---------------- TEXT INPUT ----------------
st.subheader("2. Enter or review the Tamil text")

if "input_text" not in st.session_state:
    st.session_state["input_text"] = ""

# Automatically fill the input box when text is extracted.
if extracted_text:
    st.session_state["input_text"] = extracted_text

input_text = st.text_area(
    "Tamil text",
    key="input_text",
    height=250,
    placeholder="இங்கே உங்கள் தமிழ் உரையை உள்ளிடவும்..."
)


# ---------------- CONVERSION ----------------
st.subheader("3. Convert to Simple Tamil")

if st.button("✨ Convert to Simple Tamil", type="primary"):

    if not input_text.strip():
        st.warning("Please enter text or upload a readable file.")

    else:
        try:
            with st.spinner("Converting the complete passage..."):
                simplified = simplify_tamil(input_text.strip())

            st.session_state["original_text"] = input_text.strip()
            st.session_state["simple_text"] = simplified

            st.success("Conversion completed!")

        except Exception as error:
            st.error(f"Conversion failed: {error}")


# ---------------- COMPARISON ----------------
if (
    st.session_state.get("original_text")
    and st.session_state.get("simple_text")
):
    st.subheader("4. Original vs Simple Tamil")

    left, right = st.columns(2)

    with left:
        st.markdown("### 📜 Original Tamil")

        st.text_area(
            "Original text",
            value=st.session_state["original_text"],
            height=400,
            disabled=True
        )

    with right:
        st.markdown("### 🌱 Simple Modern Tamil")

        st.text_area(
            "Simple text",
            value=st.session_state["simple_text"],
            height=400,
            disabled=True
        )

    st.caption(
        "Review the simplified text to make sure the original meaning "
        "and important details have been preserved."
    )



