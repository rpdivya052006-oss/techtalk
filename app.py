
import streamlit as st
import requests
import io
import os
from datetime import datetime

from pypdf import PdfReader
from docx import Document
from PIL import Image
import pytesseract


# --------------------------------------------------
# PAGE CONFIGURATION
# --------------------------------------------------

st.set_page_config(
    page_title="Ancient Tamil Learning Assistant",
    page_icon="📜",
    layout="wide"
)


# --------------------------------------------------
# APP TITLE
# --------------------------------------------------

st.title("📜 Ancient Tamil Learning Assistant")

st.markdown(
    """
    **Ancient Tamil → Modern Tamil → Simple Explanation**

    Understand classical Tamil poems and difficult Tamil words
    through simple Tamil explanations and voice input.
    """
)

st.divider()


# --------------------------------------------------
# API CONFIGURATION
# --------------------------------------------------

try:
    SARVAM_API_KEY = st.secrets["SARVAM_API_KEY"]
except Exception:
    SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "")


CHAT_API_URL = "https://api.sarvam.ai/v1/chat/completions"
SPEECH_API_URL = "https://api.sarvam.ai/speech-to-text"


# --------------------------------------------------
# SESSION STATE
# --------------------------------------------------

if "history" not in st.session_state:
    st.session_state["history"] = []

if "tamil_result" not in st.session_state:
    st.session_state["tamil_result"] = ""

if "poem_result" not in st.session_state:
    st.session_state["poem_result"] = ""


# --------------------------------------------------
# CHECK API KEY
# --------------------------------------------------

def check_api_key():
    if not SARVAM_API_KEY:
        st.error(
            "Sarvam API key is missing. Add SARVAM_API_KEY "
            "in Streamlit Cloud → Settings → Secrets."
        )
        return False

    return True


# --------------------------------------------------
# ANCIENT TAMIL EXPLANATION
# --------------------------------------------------

def explain_tamil_text(text, mode="text"):

    if not text.strip():
        return "Please enter Tamil text first."

    if not check_api_key():
        return None

    if mode == "poem":
        instruction = """
        You are an expert Tamil literature teacher.

        Explain the given Tamil poem using this structure:

        1. Original Tamil poem
        2. Modern Tamil version
        3. Simple Tamil explanation
        4. Meaning of difficult words
        5. Main message of the poem
        6. A simple real-life example
        7. Short summary

        Use clear, natural Tamil.
        Make the explanation suitable for students and ordinary readers.
        Do not use Tanglish.
        Do not invent details that are not supported by the poem.
        If the poem is incomplete or unclear, mention that.
        """

    else:
        instruction = """
        You are an expert Tamil language teacher.

        Explain the given Tamil text using this structure:

        1. Original text
        2. Modern Tamil version
        3. Simple Tamil explanation
        4. Meaning of difficult words
        5. Main idea
        6. A simple real-life example, if relevant
        7. Short summary

        Use clear, natural Tamil suitable for ordinary readers.
        Do not use Tanglish.
        Keep the original meaning as accurately as possible.
        If the text is unclear, mention the uncertainty.
        """

    headers = {
        "api-subscription-key": SARVAM_API_KEY,
        "Content-Type": "application/json"
    }

    payload = {
        "model": "sarvam-105b",
        "messages": [
            {
                "role": "system",
                "content": instruction
            },
            {
                "role": "user",
                "content": text
            }
        ],
        "temperature": 0.2,
        "max_tokens": 2000
    }

    try:
        response = requests.post(
            CHAT_API_URL,
            headers=headers,
            json=payload,
            timeout=120
        )

        if response.status_code != 200:
            return (
                "Explanation could not be generated.\n\n"
                f"API status: {response.status_code}\n"
                f"Details: {response.text[:1000]}"
            )

        data = response.json()

        return data["choices"][0]["message"]["content"]

    except requests.exceptions.Timeout:
        return "The request took too long. Please try again."

    except requests.exceptions.RequestException as error:
        return f"Network error: {error}"

    except (KeyError, IndexError, ValueError):
        return "The API returned an unexpected response. Please try again."


# --------------------------------------------------
# TAMIL VOICE TO TEXT
# --------------------------------------------------

def convert_voice_to_text(audio_bytes):

    if not check_api_key():
        return None

    headers = {
        "api-subscription-key": SARVAM_API_KEY
    }

    files = {
        "file": ("tamil_voice.wav", audio_bytes, "audio/wav")
    }

    data = {
        "model": "saaras:v4",
        "language_code": "ta-IN"
    }

    try:
        response = requests.post(
            SPEECH_API_URL,
            headers=headers,
            files=files,
            data=data,
            timeout=120
        )

        if response.status_code != 200:
            st.error(
                f"Voice conversion failed: {response.status_code}"
            )
            st.caption(response.text[:1000])
            return None

        result = response.json()

        return result.get("transcript", "")

    except requests.exceptions.RequestException as error:
        st.error(f"Voice service error: {error}")
        return None


# --------------------------------------------------
# READ UPLOADED FILES
# --------------------------------------------------

def extract_text_from_file(uploaded_file):

    if uploaded_file is None:
        return ""

    file_name = uploaded_file.name.lower()

    try:
        file_bytes = uploaded_file.getvalue()

        # TEXT FILE
        if file_name.endswith(".txt"):
            return file_bytes.decode("utf-8", errors="replace")

        # PDF FILE
        elif file_name.endswith(".pdf"):
            pdf = PdfReader(io.BytesIO(file_bytes))

            pages_text = []

            for page in pdf.pages:
                pages_text.append(page.extract_text() or "")

            return "\n".join(pages_text)

        # WORD DOCUMENT
        elif file_name.endswith(".docx"):
            document = Document(io.BytesIO(file_bytes))

            paragraphs = [
                paragraph.text
                for paragraph in document.paragraphs
            ]

            return "\n".join(paragraphs)

        # IMAGE OCR
        elif file_name.endswith(
            (".png", ".jpg", ".jpeg", ".tiff", ".bmp")
        ):
            image_file = Image.open(io.BytesIO(file_bytes))

            extracted_text = pytesseract.image_to_string(
                image_file,
                lang="tam+eng",
                config="--psm 6"
            )

            return extracted_text

        else:
            st.warning(
                "Unsupported file. Upload TXT, PDF, DOCX, "
                "PNG, JPG, JPEG, TIFF, or BMP."
            )
            return ""

    except Exception as error:
        st.error(f"Could not read the uploaded file: {error}")
        return ""


# --------------------------------------------------
# SAVE HISTORY
# --------------------------------------------------

def save_to_history(original_text, result, category):

    if not result:
        return

    st.session_state["history"].insert(
        0,
        {
            "time": datetime.now().strftime("%d-%m-%Y %I:%M %p"),
            "category": category,
            "original": original_text,
            "result": result
        }
    )


# --------------------------------------------------
# SIDEBAR NAVIGATION
# --------------------------------------------------

st.sidebar.title("📚 Navigation")

page = st.sidebar.radio(
    "Choose a section",
    [
        "Tamil Text Assistant",
        "Poem Learning",
        "History"
    ]
)

st.sidebar.divider()

st.sidebar.info(
    "Type Tamil text, speak in Tamil, or upload a supported file."
)


# ==================================================
# PAGE 1: TAMIL TEXT ASSISTANT
# ==================================================

if page == "Tamil Text Assistant":

    st.header("📝 Tamil Text Assistant")

    input_method = st.radio(
        "How do you want to provide your Tamil text?",
        [
            "Type / Paste Text",
            "Speak in Tamil",
            "Upload a File or Image"
        ],
        horizontal=True
    )

    original_text = ""

    # ----------------------------------------------
    # TYPE OR PASTE
    # ----------------------------------------------

    if input_method == "Type / Paste Text":

        original_text = st.text_area(
            "Enter Ancient Tamil or difficult Tamil text",
            height=180,
            placeholder="இங்கே உங்கள் தமிழ் உரையை உள்ளிடவும்..."
        )

    # ----------------------------------------------
    # SPEAK IN TAMIL
    # ----------------------------------------------

    elif input_method == "Speak in Tamil":

        st.write("🎙️ Click below and speak in Tamil.")

        audio_value = st.audio_input(
            "Record your Tamil voice"
        )

        if audio_value is not None:

            if st.button(
                "🗣️ Convert Voice to Tamil Text",
                key="convert_text_voice"
            ):

                with st.spinner("Converting your voice..."):

                    recognized_text = convert_voice_to_text(
                        audio_value.getvalue()
                    )

                if recognized_text:
                    st.session_state["recognized_text"] = recognized_text

        if "recognized_text" in st.session_state:
            original_text = st.text_area(
                "Recognized Tamil text — edit if needed",
                value=st.session_state["recognized_text"],
                height=150,
                key="recognized_text_editor"
            )

    # ----------------------------------------------
    # UPLOAD FILE OR IMAGE
    # ----------------------------------------------

    elif input_method == "Upload a File or Image":

        uploaded_file = st.file_uploader(
            "Upload TXT, PDF, DOCX, or an image",
            type=[
                "txt",
                "pdf",
                "docx",
                "png",
                "jpg",
                "jpeg",
                "tiff",
                "bmp"
            ]
        )

        if uploaded_file is not None:

            if uploaded_file.type.startswith("image/"):
                st.image(
                    uploaded_file,
                    caption="Uploaded image",
                    use_container_width=True
                )

            if st.button(
                "📄 Extract Text from File",
                key="extract_text_file"
            ):

                extracted_text = extract_text_from_file(
                    uploaded_file
                )

                st.session_state["extracted_text"] = extracted_text

            if "extracted_text" in st.session_state:
                original_text = st.text_area(
                    "Extracted text — check and edit it",
                    value=st.session_state["extracted_text"],
                    height=180,
                    key="extracted_text_editor"
                )

    # ----------------------------------------------
    # GENERATE EXPLANATION
    # ----------------------------------------------

    st.divider()

    if st.button(
        "✨ Explain in Simple Tamil",
        type="primary",
        key="explain_text_button"
    ):

        if not original_text.strip():

            st.warning("Please enter, speak, or upload some text.")

        else:

            with st.spinner(
                "Preparing the modern Tamil version and explanation..."
            ):

                result = explain_tamil_text(
                    original_text,
                    mode="text"
                )

            if result:
                st.session_state["tamil_result"] = result

                save_to_history(
                    original_text,
                    result,
                    "Tamil Text Assistant"
                )

    # ----------------------------------------------
    # DISPLAY RESULT
    # ----------------------------------------------

    if st.session_state["tamil_result"]:

        st.subheader("📖 Your Tamil Explanation")

        st.markdown(
            st.session_state["tamil_result"]
        )


# ==================================================
# PAGE 2: POEM LEARNING
# ==================================================

elif page == "Poem Learning":

    st.header("🎶 Tamil Poem Learning")

    st.write(
        "Enter a classical Tamil poem or upload a poem file/image."
    )

    poem_method = st.radio(
        "Choose your input method",
        [
            "Type a Poem",
            "Upload a Poem File or Image"
        ],
        horizontal=True
    )

    poem_text = ""

    # ----------------------------------------------
    # TYPE POEM
    # ----------------------------------------------

    if poem_method == "Type a Poem":

        poem_text = st.text_area(
            "Enter the Tamil poem",
            height=220,
            placeholder=(
                "உங்கள் பழந்தமிழ் கவிதையை இங்கே உள்ளிடவும்..."
            )
        )

    # ----------------------------------------------
    # UPLOAD POEM
    # ----------------------------------------------

    else:

        poem_file = st.file_uploader(
            "Upload a poem file or image",
            type=[
                "txt",
                "pdf",
                "docx",
                "png",
                "jpg",
                "jpeg",
                "tiff",
                "bmp"
            ],
            key="poem_file_uploader"
        )

        if poem_file is not None:

            if poem_file.type.startswith("image/"):
                st.image(
                    poem_file,
                    caption="Uploaded poem image",
                    use_container_width=True
                )

            if st.button(
                "📄 Extract Poem Text",
                key="extract_poem"
            ):

                extracted_poem = extract_text_from_file(
                    poem_file
                )

                st.session_state["extracted_poem"] = extracted_poem

            if "extracted_poem" in st.session_state:
                poem_text = st.text_area(
                    "Extracted poem — check and edit",
                    value=st.session_state["extracted_poem"],
                    height=220,
                    key="extracted_poem_editor"
                )

    # ----------------------------------------------
    # EXPLAIN POEM
    # ----------------------------------------------

    st.divider()

    if st.button(
        "🌟 Explain the Poem",
        type="primary",
        key="explain_poem_button"
    ):

        if not poem_text.strip():

            st.warning("Please enter or upload a poem first.")

        else:

            with st.spinner(
                "Explaining the poem in simple Tamil..."
            ):

                result = explain_tamil_text(
                    poem_text,
                    mode="poem"
                )

            if result:
                st.session_state["poem_result"] = result

                save_to_history(
                    poem_text,
                    result,
                    "Poem Learning"
                )

    # ----------------------------------------------
    # DISPLAY POEM RESULT
    # ----------------------------------------------

    if st.session_state["poem_result"]:

        st.subheader("📜 Poem Explanation")

        st.markdown(
            st.session_state["poem_result"]
        )


# ==================================================
# PAGE 3: HISTORY
# ==================================================

elif page == "History":

    st.header("🕘 Previous Explanations")

    if not st.session_state["history"]:

        st.info(
            "No explanations yet. Your explanations will appear here "
            "after you use the app."
        )

    else:

        if st.button(
            "🗑️ Clear History",
            key="clear_history"
        ):

            st.session_state["history"] = []
            st.session_state["tamil_result"] = ""
            st.session_state["poem_result"] = ""

            st.success("History cleared.")
            st.rerun()

        for index, item in enumerate(
            st.session_state["history"]
        ):

            with st.expander(
                f"{item['category']} — {item['time']}"
            ):

                st.markdown("**Original text:**")

                st.text(item["original"])

                st.divider()

                st.markdown("**Explanation:**")

                st.markdown(item["result"])


# --------------------------------------------------
# FOOTER
# --------------------------------------------------

st.divider()

st.caption(
    "Ancient Tamil Learning Assistant | "
    "Tamil text simplification and poem learning"
)










