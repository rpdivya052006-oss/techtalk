
import io
import os
import requests
import streamlit as st
import pytesseract

from PIL import Image
from fpdf import FPDF

# ---------------- PAGE SETTINGS ----------------
st.set_page_config(
    page_title="Ancient Tamil to Simple Tamil",
    page_icon="📚",
    layout="wide"
)

st.title("📚 Ancient Tamil to Simple Modern Tamil")
st.write(
    "Enter difficult Tamil text or upload an image. "
    "The app will rewrite it in simple, natural modern Tamil."
)

# ---------------- SARVAM API ----------------
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
                    "You are an expert Tamil language simplifier. "
                    "Rewrite the user's Tamil text in very simple, "
                    "natural, modern Tamil that ordinary people can "
                    "understand easily. Preserve the original meaning "
                    "and important facts. Explain difficult classical "
                    "words using simple Tamil where needed. Do not use "
                    "English or Tanglish. Do not add unrelated details. "
                    "Return only the simplified Tamil text."
                )
            },
            {
                "role": "user",
                "content": text
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
            f"{response.text[:500]}"
        )

    data = response.json()
    result = data["choices"][0]["message"]["content"].strip()

    if not result:
        raise ValueError(
            "Sarvam returned an empty response. Please try again."
        )

    return result


# ---------------- IMAGE OCR ----------------
def extract_tamil_from_image(image):
    try:
        return pytesseract.image_to_string(
            image,
            lang="tam+eng"
        ).strip()
    except Exception as e:
        raise RuntimeError(
            "Could not read the image. Check that Tamil OCR "
            "is installed and try a clearer image."
        ) from e


# ---------------- PDF DOWNLOAD ----------------
def create_pdf(original, simplified):
    font_path = "NotoSansTamil-Regular.ttf"

    if not os.path.exists(font_path):
        raise FileNotFoundError(
            "Add NotoSansTamil-Regular.ttf to your GitHub "
            "repository beside app.py to create a Tamil PDF."
        )

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.add_font("Tamil", fname=font_path)
    pdf.set_font("Tamil", size=12)

    # Enable Tamil text shaping if supported by the installed package
    try:
        pdf.set_text_shaping()
    except Exception:
        pass

    pdf.set_font("Tamil", size=16)
    pdf.multi_cell(0, 10, "எளிய தமிழ் விளக்கம்")
    pdf.ln(4)

    pdf.set_font("Tamil", size=12)
    pdf.multi_cell(0, 8, "அசல் உரை:")
    pdf.multi_cell(0, 8, original)
    pdf.ln(4)

    pdf.multi_cell(0, 8, "எளிய நவீன தமிழ்:")
    pdf.multi_cell(0, 8, simplified)

    output = pdf.output()
    return bytes(output)


# ---------------- INPUT OPTIONS ----------------
st.subheader("1. Enter Tamil text")

entered_text = st.text_area(
    "Paste an ancient Tamil poem, book passage, newspaper paragraph, "
    "or other difficult Tamil text:",
    height=220,
    placeholder="இங்கே உங்கள் தமிழ் உரையை உள்ளிடவும்..."
)

st.subheader("2. Or upload an image")

uploaded_image = st.file_uploader(
    "Upload a clear image containing Tamil text",
    type=["png", "jpg", "jpeg"]
)

if uploaded_image:
    image = Image.open(uploaded_image).convert("RGB")
    st.image(image, caption="Uploaded image", use_container_width=True)

    if st.button("Extract Tamil text from image"):
        with st.spinner("Reading the image..."):
            try:
                extracted = extract_tamil_from_image(image)
                if extracted:
                    st.session_state["extracted_text"] = extracted
                    st.success("Text extracted. You can review it below.")
                else:
                    st.warning(
                        "No text was detected. Try a clearer image."
                    )
            except Exception as e:
                st.error(str(e))

if "extracted_text" in st.session_state:
    st.text_area(
        "Extracted text — review and copy it into the input box above:",
        value=st.session_state["extracted_text"],
        height=150
    )

# ---------------- SIMPLIFICATION ----------------
st.subheader("3. Simplify the text")

if st.button("✨ Convert to Simple Tamil", type="primary"):
    text_to_process = entered_text.strip()

    if not text_to_process:
        st.warning(
            "Please enter the Tamil text in the text box above."
        )
    else:
        with st.spinner("Converting to simple modern Tamil..."):
            try:
                simplified = simplify_tamil(text_to_process)
                st.session_state["original_text"] = text_to_process
                st.session_state["simple_text"] = simplified
            except Exception as e:
                st.error(f"Conversion failed: {e}")

# ---------------- SIDE-BY-SIDE COMPARISON ----------------
if (
    st.session_state.get("original_text")
    and st.session_state.get("simple_text")
):
    st.subheader("4. Original vs Simple Tamil")

    left, right = st.columns(2)

    with left:
        st.markdown("### 📜 Original text")
        st.text_area(
            "Original",
            value=st.session_state["original_text"],
            height=300,
            disabled=True,
            label_visibility="collapsed"
        )

    with right:
        st.markdown("### 🌱 Simple modern Tamil")
        st.text_area(
            "Simplified",
            value=st.session_state["simple_text"],
            height=300,
            disabled=True,
            label_visibility="collapsed"
        )

    st.subheader("5. Download the result")

    try:
        pdf_bytes = create_pdf(
            st.session_state["original_text"],
            st.session_state["simple_text"]
        )

        st.download_button(
            label="📄 Download comparison as PDF",
            data=pdf_bytes,
            file_name="simple_tamil_comparison.pdf",
            mime="application/pdf"
        )
    except Exception as e:
        st.warning(str(e))

