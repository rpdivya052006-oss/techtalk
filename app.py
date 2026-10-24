
import io
import re
import requests
import streamlit as st
import pytesseract

from PIL import Image
from pypdf import PdfReader


# =========================================================
# PAGE CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="Tamil Learning Assistant",
    page_icon="📚",
    layout="wide"
)


# =========================================================
# APP TITLE
# =========================================================

st.title("📚 Ancient Tamil & Poem Learning Assistant")

st.markdown(
    """
    **Understand difficult Tamil in simple modern Tamil.**

    ✨ Tamil text simplification  
    📄 PDF and image text extraction  
    📜 Tamil poem learning  
    📖 Easy explanations and difficult-word meanings
    """
)


# =========================================================
# SARVAM API SETTINGS
# =========================================================

API_URL = "https://api.sarvam.ai/v1/chat/completions"
MODEL_NAME = "sarvam-105b"


def get_api_key():
    """Read the API key securely from Streamlit Secrets."""

    try:
        return st.secrets["SARVAM_API_KEY"]
    except Exception:
        return ""


def call_sarvam(prompt, max_tokens=3500):
    """Send a prompt to Sarvam AI and return its text response."""

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
                    "Explain Tamil literature accurately in clear, "
                    "natural Tamil. Preserve the original meaning. "
                    "Do not invent lines from poems. "
                    "Use simple Tamil that school students can understand."
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
            error_data = response.json()
            error_message = (
                error_data.get("error", {}).get("message")
                or error_data.get("message")
                or str(error_data)
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


# =========================================================
# LONG TEXT PROCESSING
# =========================================================

def split_into_chunks(text, max_chars=1800):
    """
    Split long passages into smaller chunks.
    Prefer splitting at sentence or line boundaries.
    """

    text = text.strip()

    if not text:
        return []

    chunks = []
    current = ""

    paragraphs = re.split(r"(?<=[.!?。])\s+|\n+", text)

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

            chunks.append(paragraph[:cut_position].strip())
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


def simplify_long_text(text, progress_label="Simplifying Tamil"):
    """Simplify all parts of a long passage."""

    chunks = split_into_chunks(text)

    if not chunks:
        raise RuntimeError("Please enter or upload some Tamil text.")

    simplified_chunks = []

    progress = st.progress(0)
    status = st.empty()

    for index, chunk in enumerate(chunks, start=1):
        status.write(
            f"{progress_label}: processing part "
            f"{index} of {len(chunks)}..."
        )

        prompt = f"""
Convert the following Tamil passage into simple, natural,
modern Tamil that school students can understand.

IMPORTANT:
1. Preserve the original meaning and important information.
2. Do not translate into English.
3. Do not use Tanglish or Roman letters to write Tamil.
4. Do not shorten the passage unnecessarily.
5. Do not invent facts or add unrelated information.
6. Return only the simplified Tamil text.
7. If a phrase is classical or old-fashioned, explain it
   using an appropriate modern Tamil expression.

Tamil passage:

{chunk}
"""

        answer = call_sarvam(prompt, max_tokens=3500)
        simplified_chunks.append(answer)

        progress.progress(index / len(chunks))

    status.success("Tamil simplification completed!")

    return "\n\n".join(simplified_chunks)


# =========================================================
# TEXT EXTRACTION FROM UPLOADED FILES
# =========================================================

def extract_text_from_image(uploaded_file):
    """Extract Tamil and English text from an image using OCR."""

    image_bytes = uploaded_file.getvalue()
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

    try:
        extracted_text = pytesseract.image_to_string(
            image,
            lang="tam+eng"
        )
    except Exception as error:
        raise RuntimeError(
            "Tamil OCR failed. Check packages.txt and make sure "
            "Tamil Tesseract language support is installed. "
            f"Details: {error}"
        )

    if not extracted_text.strip():
        raise RuntimeError(
            "No text was detected. Please upload a clearer image."
        )

    return extracted_text.strip()


def extract_text_from_pdf(uploaded_file):
    """Extract selectable text from a PDF."""

    pdf_bytes = io.BytesIO(uploaded_file.getvalue())

    try:
        reader = PdfReader(pdf_bytes)
        page_texts = []

        for page in reader.pages:
            page_texts.append(page.extract_text() or "")

        extracted_text = "\n\n".join(page_texts).strip()

    except Exception as error:
        raise RuntimeError(f"Could not read the PDF: {error}")

    if not extracted_text:
        raise RuntimeError(
            "No selectable text was found in this PDF. "
            "If it is a scanned PDF, save the page as an image "
            "and upload the JPG or PNG instead."
        )

    return extracted_text


# =========================================================
# BUILT-IN TAMIL POEM COLLECTION
# =========================================================

POEMS = {
    "யாதும் ஊரே யாவரும் கேளிர் — கணியன் பூங்குன்றனார்": {
        "author": "கணியன் பூங்குன்றனார்",
        "period": "சங்க இலக்கியம் — புறநானூறு",
        "poem": """யாதும் ஊரே யாவரும் கேளிர்
தீதும் நன்றும் பிறர்தர வாரா
நோதலும் தணிதலும் அவற்றோரன்ன
சாதலும் புதுவது அன்றே
வாழ்தல் இனிதென மகிழ்ந்தன்றும் இலமே
முனிவின் இன்னாது என்றலும் இலமே""",
        "note": (
            "இது புறநானூற்றில் இடம்பெறும் புகழ்பெற்ற பாடலின் "
            "தொடக்கப் பகுதிகளைக் கொண்ட எடுத்துக்காட்டு. "
            "முழுப் பாடலின் விளக்கத்திற்கு நம்பகமான பாடநூல் "
            "அல்லது பதிப்பைப் பயன்படுத்தவும்."
        )
    },

    "கற்க கசடற — திருவள்ளுவர்": {
        "author": "திருவள்ளுவர்",
        "period": "திருக்குறள் — கல்வி",
        "poem": "கற்க கசடறக் கற்பவை கற்றபின்\nநிற்க அதற்குத் தக.",
        "note": (
            "திருக்குறள் 391. கல்வியைப் பிழையின்றிக் கற்று, "
            "கற்றதற்கேற்ப வாழ வேண்டும் என்பதே கருத்து."
        )
    },

    "அகர முதல — திருவள்ளுவர்": {
        "author": "திருவள்ளுவர்",
        "period": "திருக்குறள் — கடவுள் வாழ்த்து",
        "poem": "அகர முதல எழுத்தெல்லாம் ஆதி\nபகவன் முதற்றே உலகு.",
        "note": (
            "திருக்குறள் 1. எழுத்துகளுக்கு அகரம் முதன்மையானது போல, "
            "உலகிற்கு இறைவன் முதன்மையானவர் என்று இந்தக் குறள் கூறுகிறது."
        )
    },

    "தீயினால் சுட்ட புண் — திருவள்ளுவர்": {
        "author": "திருவள்ளுவர்",
        "period": "திருக்குறள் — இன்னா செய்யாமை",
        "poem": (
            "தீயினால் சுட்ட புண் உள்ளாறும் ஆறாதே\n"
            "நாவினால் சுட்ட வடு."
        ),
        "note": (
            "திருக்குறள் 129. தீயால் ஏற்பட்ட காயம் ஆறலாம்; "
            "ஆனால் கடுமையான சொற்களால் ஏற்பட்ட மனக்காயம் எளிதில் ஆறாது."
        )
    },

    "ஒழுக்கம் விழுப்பம் தரலான் — திருவள்ளுவர்": {
        "author": "திருவள்ளுவர்",
        "period": "திருக்குறள் — ஒழுக்கமுடைமை",
        "poem": "ஒழுக்கம் விழுப்பம் தரலான் ஒழுக்கம்\nஉயிரினும் ஓம்பப் படும்.",
        "note": (
            "திருக்குறள் 131. ஒழுக்கம் மனிதனுக்குப் பெருமை தருவதால், "
            "அதை உயிரைவிட முக்கியமாகக் காக்க வேண்டும்."
        )
    }
}


# =========================================================
# MAIN NAVIGATION
# =========================================================

tab_text, tab_poem = st.tabs([
    "📝 Tamil Text Simplifier",
    "📜 Tamil Poem Learning"
])


# =========================================================
# TAB 1 — EXISTING TEXT SIMPLIFIER
# =========================================================

with tab_text:

    st.header("📝 Convert Difficult Tamil into Simple Tamil")

    st.write(
        "Type Tamil text or upload a PDF/image. "
        "The app extracts the text and simplifies it for students."
    )

    input_method = st.radio(
        "Choose your input method:",
        ["Type or paste text", "Upload PDF or image"],
        horizontal=True,
        key="text_input_method"
    )

    original_text = ""

    if input_method == "Type or paste text":

        original_text = st.text_area(
            "Enter your Tamil text here:",
            height=250,
            placeholder="இங்கே தமிழ் உரையை உள்ளிடவும்...",
            key="manual_tamil_text"
        )

    else:

        uploaded_file = st.file_uploader(
            "Upload a PDF, JPG, JPEG, or PNG file",
            type=["pdf", "jpg", "jpeg", "png"],
            key="text_file_upload"
        )

        if uploaded_file is not None:

            file_name = uploaded_file.name.lower()

            try:
                if file_name.endswith(".pdf"):
                    original_text = extract_text_from_pdf(uploaded_file)
                else:
                    original_text = extract_text_from_image(uploaded_file)

                st.success("Text extracted successfully!")

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

            st.warning("Please enter Tamil text or upload a file.")

        else:

            try:
                with st.spinner(
                    "Converting into simple modern Tamil..."
                ):
                    simplified_text = simplify_long_text(
                        original_text,
                        progress_label="Simplifying passage"
                    )

                st.subheader("📖 Original and Simplified Tamil")

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


# =========================================================
# TAB 2 — POEM LEARNING
# =========================================================

with tab_poem:

    st.header("📜 Tamil Poem Learning")

    st.write(
        "Choose a poem from the collection or enter your own poem. "
        "The app explains the poem in simple modern Tamil."
    )

    poem_mode = st.radio(
        "Choose how to provide the poem:",
        [
            "Choose from poem collection",
            "Enter my own poem"
        ],
        horizontal=True,
        key="poem_mode"
    )

    poem_title = ""
    poem_author = ""
    poem_text = ""

    if poem_mode == "Choose from poem collection":

        poem_title = st.selectbox(
            "Select a Tamil poem:",
            list(POEMS.keys()),
            key="poem_selector"
        )

        selected_poem = POEMS[poem_title]

        poem_author = selected_poem["author"]
        poem_text = selected_poem["poem"]

        st.caption(
            f"Author: {poem_author} | "
            f"Literature: {selected_poem['period']}"
        )

        st.markdown("#### Original Poem")
        st.text_area(
            "Selected poem",
            value=poem_text,
            height=180,
            key="selected_poem_preview"
        )

        st.info(selected_poem["note"])

    else:

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
            height=220,
            placeholder="இங்கே முழுத் தமிழ்ப் பாடலையும் உள்ளிடவும்...",
            key="custom_poem_text"
        )

    st.markdown("---")

    explain_poem = st.button(
        "📚 Explain Poem in Simple Tamil",
        type="primary",
        key="explain_poem_button"
    )

    if explain_poem:

        if not poem_text.strip():

            st.warning("Please select or enter a Tamil poem.")

        else:

            try:

                poem_prompt = f"""
You are a Tamil literature teacher helping school students.

Explain the following poem in SIMPLE, NATURAL MODERN TAMIL.

Poem title: {poem_title or "Not provided"}
Poet: {poem_author or "Not provided"}

ORIGINAL POEM:
{poem_text}

Give the answer using exactly these headings:

### 1. எளிய நவீன தமிழ்
Rewrite the poem's meaning in simple modern Tamil.
Preserve the original ideas. Do not invent new lines.
Keep the explanation suitable for students.

### 2. பாடலின் மொத்தப் பொருள்
Explain the central meaning of the poem in simple Tamil.
Explain what the poet wants readers to understand.

### 3. கடினமான சொற்களின் பொருள்
List important difficult words from the actual poem
and explain each in simple Tamil.
Use a bullet list in this format:
- சொல்லின் பொருள்: எளிய விளக்கம்

Only include words that genuinely appear in the poem.
If a word has multiple meanings, explain the meaning
that best fits this poem.

### 4. மாணவர்கள் கற்றுக்கொள்ள வேண்டியது
Give 2 to 4 short points about the lesson or message
students can learn from the poem.

### 5. சிறிய சுருக்கம்
Give a short, easy-to-remember summary in Tamil.

IMPORTANT:
- Write the answer in Tamil script.
- Do not use Tanglish.
- Do not translate the answer into English.
- Do not claim that your interpretation is the only possible one.
- Do not fabricate missing poem lines or historical facts.
- If the supplied poem is incomplete, explain only the supplied text.
"""

                with st.spinner(
                    "Understanding the poem and preparing "
                    "the student-friendly explanation..."
                ):

                    poem_explanation = call_sarvam(
                        poem_prompt,
                        max_tokens=3500
                    )

                st.success("Poem explanation is ready!")

                st.markdown("## 📜 Original Poem")

                if poem_title:
                    st.markdown(f"**{poem_title}**")

                st.text_area(
                    "Original poem text",
                    value=poem_text,
                    height=180,
                    key="poem_original_result"
                )

                st.markdown("## 🎓 Student-Friendly Explanation")

                st.markdown(poem_explanation)

            except Exception as error:
                st.error(str(error))


# =========================================================
# FOOTER
# =========================================================

st.markdown("---")

st.caption(
    "Tamil Learning Assistant | Powered by Sarvam AI | "
    "For educational use. Verify poem text and interpretations "
    "with your textbook or a trusted Tamil literature source."
)





