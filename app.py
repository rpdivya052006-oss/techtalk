
import streamlit as st
import requests
import os
import io
from PIL import Image
import pytesseract
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

st.set_page_config(
    page_title="Rural ACT - Simple Tamil",
    page_icon="📖",
    layout="wide"
)

st.title("📖 Rural ACT – Simple Tamil Converter")
st.write("Convert difficult Tamil passages into very simple modern Tamil.")

st.info(
    "Paste Tamil text or upload a Tamil image. "
    "Get a simple explanation and download it as a PDF."
)

# API configuration
api_key = st.secrets.get("SARVAM_API_KEY", os.getenv("SARVAM_API_KEY", ""))

def simplify_tamil(text):
    if not api_key:
        st.error("Please add SARVAM_API_KEY in Streamlit Secrets.")
        return ""

    url = "https://api.sarvam.ai/translate"

    headers = {
        "api-subscription-key": api_key,
        "Content-Type": "application/json"
    }

    payload = {
        "input": text,
        "source_language_code": "ta-IN",
        "target_language_code": "ta-IN",
        "mode": "formal",
        "model": "mayura:v1",
        "enable_preprocessing": True
    }

    try:
        response = requests.post(
            url, headers=headers, json=payload, timeout=60
        )
        response.raise_for_status()
        result = response.json()
        return result.get("translated_text", "")

    except Exception as e:
        st.error(f"Text processing failed: {e}")
        return ""

# Input methods
st.subheader("1. Enter or upload Tamil content")

input_method = st.radio(
    "Choose input method",
    ["Type or paste text", "Upload an image"],
    horizontal=True
)

original_text = ""

if input_method == "Type or paste text":
    original_text = st.text_area(
        "Enter Tamil paragraph",
        height=200,
        placeholder="இங்கே தமிழ் பத்தியை உள்ளிடவும்..."
    )

else:
    uploaded_image = st.file_uploader(
        "Upload a Tamil newspaper or book image",
        type=["png", "jpg", "jpeg"]
    )

    if uploaded_image:
        image = Image.open(uploaded_image)
        st.image(image, caption="Uploaded image", width=400)

        try:
            original_text = pytesseract.image_to_string(
                image, lang="tam+eng"
            )
            st.subheader("Extracted text")
            original_text = st.text_area(
                "Check and correct the extracted Tamil text",
                value=original_text,
                height=200
            )
        except Exception as e:
            st.error(
                "Image text extraction failed. "
                "Check the OCR installation and Tamil language data."
            )

# Simplification
if st.button("✨ Convert to Simple Tamil", type="primary"):
    if not original_text.strip():
        st.warning("Please enter text or upload an image.")
    else:
        with st.spinner("Converting to simple Tamil..."):
            simplified_text = simplify_tamil(original_text)

        if simplified_text:
            st.session_state["original"] = original_text
            st.session_state["simplified"] = simplified_text

# Display comparison
if "simplified" in st.session_state:
    st.subheader("2. Original vs. Simple Tamil")

    left, right = st.columns(2)

    with left:
        st.markdown("### Original Tamil")
        st.text_area(
            "Original text",
            value=st.session_state["original"],
            height=300,
            disabled=True,
            key="original_display"
        )

    with right:
        st.markdown("### Simple Modern Tamil")
        st.text_area(
            "Simplified text",
            value=st.session_state["simplified"],
            height=300,
            disabled=True,
            key="simple_display"
        )

    # PDF download
    st.subheader("3. Download your result")

    st.caption(
        "For correct Tamil characters in the PDF, "
        "a Unicode Tamil font must be installed and registered."
    )

    font_path = "NotoSansTamil-Regular.ttf"

    if os.path.exists(font_path):
        pdfmetrics.registerFont(TTFont("TamilFont", font_path))

        buffer = io.BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=A4)
        pdf.setFont("TamilFont", 12)

        width, height = A4
        y = height - 50

        for heading, content in [
            ("Original Tamil", st.session_state["original"]),
            ("Simple Modern Tamil", st.session_state["simplified"])
        ]:
            if y < 80:
                pdf.showPage()
                pdf.setFont("TamilFont", 12)
                y = height - 50

            pdf.drawString(40, y, heading)
            y -= 25

            for line in content.splitlines():
                if y < 50:
                    pdf.showPage()
                    pdf.setFont("TamilFont", 12)
                    y = height - 50

                pdf.drawString(40, y, line[:90])
                y -= 20

            y -= 30

        pdf.save()
        buffer.seek(0)

        st.download_button(
            "📄 Download PDF",
            data=buffer.getvalue(),
            file_name="Rural_ACT_Simple_Tamil.pdf",
            mime="application/pdf"
        )
    else:
        st.warning(
            "Add NotoSansTamil-Regular.ttf to your app folder "
            "to enable Tamil PDF downloads."
        )
