
import io
import requests
import streamlit as st
import pytesseract

from PIL import Image
from pypdf import PdfReader

st.set_page_config(
    page_title="Ancient Tamil to Simple Tamil",
    page_icon="📚",
    layout="wide"
)

st.title("📚 Ancient Tamil to Simple Modern Tamil")
st.write(
    "Upload a PDF or image, or enter Tamil text. "
    "Convert difficult Tamil into simple, natural modern Tamil."
)


# -------- SARVAM API --------
def simplify_tamil(text):
    api_key = st.secrets.get("SARVAM_API_KEY", "")

    if not api_key:
        raise ValueError(
            "SARVAM_API_KEY is missing. Add it in Streamlit Secrets."
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
                    "Rewrite the given Tamil text in very simple, "
                    "natural modern Tamil. Preserve its original meaning "
                    "and important facts. Explain difficult classical "
                    "words in simple Tamil where necessary. Do not use "
                    "Tanglish or unrelated details. Return only the "
                    "simplified Tamil text."
                )
            },
            {"role": "user", "content": text}
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
            f"{response.text[:500]}"
        )

    data = response.json()
    return data["choices"][0]["message"]["content"].strip()


# -------- IMAGE TEXT EXTRACTION --------
def extract_from_image(image):
    return pytesseract.image_to_string(
        image,
        lang="tam+eng"
    ).strip()


# -------- PDF TEXT EXTRACTION --------
def extract_from_pdf(uploaded_file):
    reader = PdfReader(uploaded_file)
    pages = []

    for page in reader.pages:
        page_text = page.extract_text() or ""
        pages.append(page_text)

    return "\n\n".join(pages).strip()


# -------- FILE UPLOAD --------
st.subheader("1. Upload a PDF or image")

uploaded_file = st.file_uploader(
    "Choose a Tamil text file",
    type=["pdf", "jpg", "jpeg", "png"]
)

extracted_text = ""

if uploaded_file:
    file_type = uploaded_file.name.lower()

    try:
        if file_type.endswith(".pdf"):
            extracted_text = extract_from_pdf(uploaded_file)

            if not extracted_text:
                st.warning(
                    "No selectable text found in this PDF. "
                    "If it is a scanned PDF, upload its pages as JPG "
                    "or PNG images for OCR."
                )

        else:
            image_file = Image.open(uploaded_file).convert("RGB")
            st.image(
                image_file,
                caption="Uploaded image",
                use_container_width=True
            )
            extracted_text = extract_from_image(image_file)

        if extracted_text:
            st.success("Text extracted successfully.")

    except Exception as e:
        st.error(f"Could not read this file: {e}")


# -------- TEXT INPUT --------
st.subheader("2. Enter or review Tamil text")

default_text = extracted_text or st.session_state.get(
    "input_text", ""
)

input_text = st.text_area(
    "Tamil text",
    value=default_text,
    height=220,
    placeholder="இங்கே தமிழ் உரையை உள்ளிடவும்..."
)

# -------- SIMPLIFY --------
st.subheader("3. Convert to simple Tamil")

if st.button("✨ Convert to Simple Tamil", type="primary"):
    if not input_text.strip():
        st.warning("Please enter Tamil text or upload a readable file.")

    else:
        with st.spinner("Converting with Sarvam AI..."):
            try:
                result = simplify_tamil(input_text.strip())
                st.session_state["original_text"] = input_text.strip()
                st.session_state["simple_text"] = result

            except Exception as e:
                st.error(f"Conversion failed: {e}")


# -------- SIDE-BY-SIDE COMPARISON --------
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
            height=300,
            disabled=True
        )

    with right:
        st.markdown("### 🌱 Simple Modern Tamil")
        st.text_area(
            "Simple text",
            value=st.session_state["simple_text"],
            height=300,
            disabled=True
        )


