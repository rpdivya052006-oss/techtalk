
import io
import os
import re
from pathlib import Path
from xml.sax.saxutils import escape

import fitz
import pytesseract
import requests
import streamlit as st
from PIL import Image, ImageOps, ImageFilter
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ---------------- PAGE SETUP ----------------

st.set_page_config(
    page_title="Rural ACT - Simple Tamil",
    page_icon="📘",
    layout="wide"
)

st.title("📘 Rural ACT - தமிழ் எளிமைப்படுத்தி")
st.caption(
    "Ancient Tamil, poems and difficult Tamil text "
    "converted into simple modern Tamil."
)

st.write(
    "Enter Tamil text or upload a Tamil PDF/image. "
    "There is no poem collection selection option."
)

SARVAM_URL = "https://api.sarvam.ai/v1/chat/completions"
MAX_CHARS = 3500


# ---------------- API KEY ----------------

def get_api_key():
    try:
        key = st.secrets.get("SARVAM_API_KEY", "")
        if key:
            return key
    except Exception:
        pass

    return os.getenv("SARVAM_API_KEY", "")


# ---------------- SARVAM API ----------------

def call_sarvam(prompt, api_key):
    response = requests.post(
        SARVAM_URL,
        headers={
            "api-subscription-key": api_key,
            "Content-Type": "application/json"
        },
        json={
            "model": "sarvam-m",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a careful Tamil language teacher. "
                        "Respond in Tamil script. Use simple language "
                        "and do not invent facts."
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.2
        },
        timeout=120
    )

    if response.status_code >= 400:
        raise RuntimeError(
            f"Sarvam API error {response.status_code}: "
            f"{response.text[:400]}"
        )

    data = response.json()

    try:
        result = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise RuntimeError(
            "Unexpected response from Sarvam AI."
        )

    if isinstance(result, list):
        result = "\n".join(
            str(item.get("text", ""))
            if isinstance(item, dict)
            else str(item)
            for item in result
        )

    result = str(result).strip()

    if not result:
        raise RuntimeError("Sarvam returned an empty response.")

    return result


# ---------------- LONG TEXT SUPPORT ----------------

def split_long_text(text, max_chars=MAX_CHARS):
    text = text.strip()

    if len(text) <= max_chars:
        return [text]

    paragraphs = [
        part.strip()
        for part in re.split(r"\n\s*\n", text)
        if part.strip()
    ]

    chunks = []
    current = ""

    for paragraph in paragraphs:
        if len(paragraph) > max_chars:
            if current:
                chunks.append(current)
                current = ""

            for start in range(0, len(paragraph), max_chars):
                chunks.append(
                    paragraph[start:start + max_chars]
                )

        elif not current:
            current = paragraph

        elif len(current) + len(paragraph) + 2 <= max_chars:
            current += "\n\n" + paragraph

        else:
            chunks.append(current)
            current = paragraph

    if current:
        chunks.append(current)

    return chunks


# ---------------- SIMPLE TAMIL ----------------

def simplify_tamil(text, api_key):
    chunks = split_long_text(text)
    results = []

    for index, chunk in enumerate(chunks, start=1):
        prompt = (
            "Rewrite the following Tamil text in very simple, "
            "natural, modern Tamil. Preserve the original meaning, "
            "names, dates and numbers. Do not translate into English. "
            "Do not add new facts. Use short sentences and common "
            "Tamil words. Return only the simplified Tamil text.\n\n"
            "Tamil text:\n" + chunk
        )

        with st.spinner(
            f"Simplifying text ({index}/{len(chunks)})..."
        ):
            results.append(
                call_sarvam(prompt, api_key)
            )

    return "\n\n".join(results)


# ---------------- POEM EXPLANATION ----------------

def explain_poem(text, api_key):
    prompt = (
        "Explain the following Tamil poem or ancient Tamil passage "
        "for students in Tamil. Preserve the original poem's meaning. "
        "Do not invent historical facts or author details. "
        "Use these headings in Tamil:\n"
        "1. எளிய நவீன தமிழ்\n"
        "2. பாடலின் எளிய விளக்கம்\n"
        "3. கடினமான சொற்களின் பொருள்\n"
        "4. பாடல் சொல்லும் முக்கியக் கருத்து\n\n"
        "Explain difficult words in a list. Use clear, simple Tamil. "
        "Do not change the original poem itself.\n\n"
        "Poem:\n" + text
    )

    return call_sarvam(prompt, api_key)


# ---------------- IMAGE TEXT EXTRACTION ----------------

def prepare_image(image):
    image = image.convert("RGB")
    image = ImageOps.grayscale(image)
    image = ImageOps.autocontrast(image)
    return image.filter(ImageFilter.SHARPEN)


def extract_image_text(uploaded_file):
    image = prepare_image(
        Image.open(uploaded_file)
    )

    return pytesseract.image_to_string(
        image,
        lang="tam+eng",
        config="--psm 6"
    ).strip()


# ---------------- PDF TEXT EXTRACTION ----------------

def extract_pdf_text(uploaded_file):
    document = fitz.open(
        stream=uploaded_file.getvalue(),
        filetype="pdf"
    )

    pages = []

    for page_number, page in enumerate(document, start=1):
        text = page.get_text("text").strip()

        # OCR for scanned PDF pages
        if not text:
            pix = page.get_pixmap(
                matrix=fitz.Matrix(2, 2),
                alpha=False
            )

            image = Image.open(
                io.BytesIO(pix.tobytes("png"))
            )

            image = prepare_image(image)

            text = pytesseract.image_to_string(
                image,
                lang="tam+eng",
                config="--psm 6"
            ).strip()

        if text:
            pages.append(
                f"[Page {page_number}]\n{text}"
            )

    document.close()

    return "\n\n".join(pages).strip()


# ---------------- TAMIL FONT ----------------

def find_tamil_font():
    candidates = [
        "/usr/share/fonts/truetype/noto/"
        "NotoSansTamil-Regular.ttf",
        "/usr/share/fonts/truetype/noto/"
        "NotoSansTamilUI-Regular.ttf",
        "/usr/share/fonts/opentype/noto/"
        "NotoSansTamil-Regular.ttf",
        "/usr/share/fonts/truetype/lohit-tamil/"
        "Lohit-Tamil.ttf",
        "NotoSansTamil-Regular.ttf"
    ]

    for font in candidates:
        if Path(font).exists():
            return font

    for root in ("/usr/share/fonts", "."):
        try:
            for font in Path(root).rglob(
                "*Tamil*Regular.ttf"
            ):
                return str(font)
        except Exception:
            pass

    return None


# ---------------- CREATE PDF ----------------

def make_pdf(original, result):
    buffer = io.BytesIO()

    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm
    )

    styles = getSampleStyleSheet()

    styles.add(
        ParagraphStyle(
            name="TamilTitle",
            parent=styles["Title"],
            alignment=TA_CENTER,
            fontSize=16,
            leading=24,
            spaceAfter=15
        )
    )

    styles.add(
        ParagraphStyle(
            name="TamilHeading",
            parent=styles["Heading2"],
            fontSize=12,
            leading=18,
            spaceBefore=8,
            spaceAfter=6
        )
    )

    styles.add(
        ParagraphStyle(
            name="TamilBody",
            parent=styles["BodyText"],
            fontSize=11,
            leading=18,
            spaceAfter=8,
            wordWrap="CJK"
        )
    )

    font_path = find_tamil_font()

    if not font_path:
        raise RuntimeError(
            "Tamil font not found. Check packages.txt."
        )

    try:
        pdfmetrics.registerFont(
            TTFont("TamilFont", font_path)
        )
    except Exception:
        pass

    for name in (
        "TamilTitle",
        "TamilHeading",
        "TamilBody"
    ):
        styles[name].fontName = "TamilFont"

    story = [
        Paragraph(
            "Rural ACT - எளிய தமிழ்",
            styles["TamilTitle"]
        )
    ]

    for heading, content in [
        ("Original Tamil Text", original),
        ("Simple Tamil / Poem Explanation", result)
    ]:
        story.append(
            Paragraph(
                escape(heading),
                styles["TamilHeading"]
            )
        )

        for line in content.splitlines():
            if line.strip():
                story.append(
                    Paragraph(
                        escape(line),
                        styles["TamilBody"]
                    )
                )

        story.append(Spacer(1, 3 * mm))

    document.build(story)

    return buffer.getvalue()


# ---------------- API KEY INSTRUCTIONS ----------------

with st.expander("Sarvam API Key Setup"):
    st.write(
        "In Streamlit Cloud, open App settings > Secrets "
        "and add your API key:"
    )

    st.code(
        'SARVAM_API_KEY = "your_sarvam_api_key"',
        language="toml"
    )

    st.caption(
        "Do not write your secret API key directly in app.py."
    )


# ---------------- FILE UPLOAD ----------------

uploaded_file = st.file_uploader(
    "Upload a Tamil PDF or image (optional)",
    type=["pdf", "png", "jpg", "jpeg", "webp"]
)

if uploaded_file:
    if uploaded_file.name.lower().endswith(".pdf"):
        st.info(
            f"Uploaded PDF: {uploaded_file.name}"
        )
    else:
        st.image(
            uploaded_file,
            caption="Uploaded image",
            use_container_width=True
        )

    if st.button("Extract Tamil Text from File"):
        try:
            with st.spinner("Extracting text..."):
                if uploaded_file.name.lower().endswith(".pdf"):
                    extracted = extract_pdf_text(
                        uploaded_file
                    )
                else:
                    extracted = extract_image_text(
                        uploaded_file
                    )

            if extracted:
                st.session_state["extracted_text"] = extracted
                st.success(
                    "Text extracted. Check it below."
                )
            else:
                st.warning(
                    "No text found. Try a clearer file."
                )

        except Exception as exc:
            st.error(
                f"Text extraction failed: {exc}"
            )


# ---------------- USER INPUT ----------------

original_text = st.text_area(
    "Enter Tamil text or poem",
    value=st.session_state.get(
        "extracted_text", ""
    ),
    height=240,
    placeholder="Paste your Tamil text or poem here..."
)

poem_mode = st.checkbox(
    "This is an ancient Tamil poem. Explain it and give difficult word meanings.",
    value=False
)


# ---------------- PROCESS TEXT ----------------

if st.button(
    "Simplify Tamil",
    type="primary",
    use_container_width=True
):
    if not original_text.strip():
        st.warning(
            "Please enter Tamil text or upload a file first."
        )

    else:
        api_key = get_api_key()

        if not api_key:
            st.error(
                "Sarvam API key is missing. Add "
                "SARVAM_API_KEY in Streamlit Cloud Secrets."
            )

        else:
            try:
                clean_text = original_text.strip()

                if poem_mode:
                    result = explain_poem(
                        clean_text, api_key
                    )
                else:
                    result = simplify_tamil(
                        clean_text, api_key
                    )

                st.session_state["original_result"] = clean_text
                st.session_state["simple_result"] = result
                st.session_state["poem_mode"] = poem_mode

                st.success("Processing completed!")

            except requests.RequestException as exc:
                st.error(
                    f"Internet or API connection error: {exc}"
                )

            except Exception as exc:
                st.error(
                    f"Could not process the text: {exc}"
                )


# ---------------- DISPLAY RESULTS ----------------

if st.session_state.get("simple_result"):
    st.subheader("Result")

    left, right = st.columns(2)

    with left:
        st.markdown("### Original Tamil")

        st.text_area(
            "Original text",
            value=st.session_state["original_result"],
            height=350,
            key="original_display"
        )

    with right:
        if st.session_state.get("poem_mode"):
            st.markdown(
                "### Modern Tamil and Poem Explanation"
            )
        else:
            st.markdown("### Simple Modern Tamil")

        st.text_area(
            "Processed text",
            value=st.session_state["simple_result"],
            height=400,
            key="simple_display"
        )

    try:
        pdf_data = make_pdf(
            st.session_state["original_result"],
            st.session_state["simple_result"]
        )

        st.download_button(
            "Download Result as PDF",
            data=pdf_data,
            file_name="Rural_ACT_Simple_Tamil.pdf",
            mime="application/pdf",
            use_container_width=True
        )

    except Exception as exc:
        st.warning(
            f"PDF creation failed. Check Tamil fonts: {exc}"
        )


# ---------------- FOOTER ----------------

st.divider()

st.caption(
    "OCR may contain errors. Check extracted text before using it. "
    "AI-generated explanations should also be reviewed."
)






