

import streamlit as st
import requests
import pytesseract
from PIL import Image, ImageOps, ImageEnhance
from io import BytesIO
from datetime import datetime
from pypdf import PdfReader
from docx import Document

# =====================================================
# PAGE SETTINGS
# =====================================================

st.set_page_config(
    page_title="Ancient Tamil Learning Assistant",
    page_icon="📜",
    layout="wide"
)

st.title("📜 Ancient Tamil Learning Assistant")
st.write(
    "Speak, type, upload documents or images, and learn "
    "Ancient Tamil in simple modern Tamil."
)

# =====================================================
# SESSION STATE
# =====================================================

defaults = {
    "tamil_text": "",
    "tamil_result": "",
    "poem_text": "",
    "poem_result": "",
    "history": []
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


# =====================================================
# API KEY
# =====================================================

def get_api_key():
    try:
        return st.secrets["SARVAM_API_KEY"]
    except Exception:
        return None


# =====================================================
# VOICE TO TEXT
# =====================================================

def transcribe_tamil_audio(audio_bytes, api_key):
    response = requests.post(
        "https://api.sarvam.ai/speech-to-text",
        headers={"api-subscription-key": api_key},
        files={
            "file": (
                "tamil_voice.wav",
                audio_bytes,
                "audio/wav"
            )
        },
        data={
            "model": "saaras:v4",
            "mode": "transcribe",
            "language_code": "ta-IN"
        },
        timeout=120
    )

    response.raise_for_status()
    return response.json().get("transcript", "").strip()


# =====================================================
# IMAGE OCR
# =====================================================

def extract_image_text(uploaded_file):
    image = Image.open(
        BytesIO(uploaded_file.getvalue())
    ).convert("RGB")

    # Improve contrast to help OCR read the text.
    image = ImageOps.grayscale(image)
    image = ImageEnhance.Contrast(image).enhance(1.5)

    text = pytesseract.image_to_string(
        image,
        lang="tam+eng",
        config="--psm 6"
    ).strip()

    if not text:
        raise ValueError(
            "No text could be detected. Please upload a clearer "
            "image with readable Tamil letters."
        )

    return text


# =====================================================
# DOCUMENT TEXT EXTRACTION
# =====================================================

def extract_text(uploaded_file):
    filename = uploaded_file.name.lower()
    data = uploaded_file.getvalue()

    if filename.endswith(".txt"):
        return data.decode("utf-8-sig")

    if filename.endswith(".pdf"):
        pdf = PdfReader(BytesIO(data))

        text = "\n".join(
            page.extract_text() or ""
            for page in pdf.pages
        ).strip()

        if not text:
            raise ValueError(
                "No selectable text found in this PDF. "
                "Try uploading a page as PNG or JPG instead."
            )

        return text

    if filename.endswith(".docx"):
        document = Document(BytesIO(data))

        return "\n".join(
            paragraph.text
            for paragraph in document.paragraphs
            if paragraph.text.strip()
        )

    if filename.endswith((".png", ".jpg", ".jpeg")):
        return extract_image_text(uploaded_file)

    raise ValueError(
        "Supported formats: TXT, PDF, DOCX, PNG, JPG, JPEG."
    )


# =====================================================
# ANCIENT TAMIL EXPLANATION
# =====================================================

def simplify_tamil(text, api_key, is_poem=False):

    if is_poem:
        task = """
Explain this Ancient Tamil poem.
Preserve the original meaning.
Explain each line in simple modern Tamil.
Explain difficult words and the overall message.
Do not invent missing lines or uncertain meanings.
"""
    else:
        task = """
Rewrite this text in simple modern Tamil.
Explain difficult words and the overall meaning.
Preserve the original meaning.
Do not invent uncertain information.
"""

    prompt = f"""
You are an expert Tamil language and literature teacher.

{task}

Answer in Tamil script, not Tanglish.

Use these headings:

1. எளிய நவீன தமிழ்
2. கடினமான சொற்களின் பொருள்
3. வரி வாரியான விளக்கம்
4. மொத்தக் கருத்து
5. சுருக்கம்
6. கற்றுக்கொள்ள வேண்டிய கருத்து

Original Tamil text:
{text}
"""

    response = requests.post(
        "https://api.sarvam.ai/v1/chat/completions",
        headers={
            "api-subscription-key": api_key,
            "Content-Type": "application/json"
        },
        json={
            "model": "sarvam-105b",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a careful Tamil literature teacher. "
                        "Explain clearly in simple modern Tamil."
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.2,
            "max_tokens": 3000
        },
        timeout=180
    )

    response.raise_for_status()
    result = response.json()

    return result["choices"][0]["message"]["content"].strip()


# =====================================================
# SAVE HISTORY
# =====================================================

def save_history(kind, original_text, result):
    st.session_state["history"].append({
        "type": kind,
        "time": datetime.now().strftime("%d-%m-%Y %I:%M %p"),
        "text": original_text,
        "result": result
    })


# =====================================================
# SIDEBAR MENU
# =====================================================

st.sidebar.title("📚 Menu")

page = st.sidebar.radio(
    "Choose a section",
    [
        "Tamil Text Assistant",
        "Poem Learning",
        "History"
    ]
)


# =====================================================
# HISTORY
# =====================================================

if page == "History":

    st.header("🕘 Learning History")

    history = st.session_state["history"]

    if not history:
        st.info(
            "No history yet. Process text or a poem to see it here."
        )

    else:
        st.write(f"Saved results: {len(history)}")

        if st.button("🗑️ Clear History"):
            st.session_state["history"] = []
            st.rerun()

        for index, item in enumerate(reversed(history)):

            with st.expander(
                f"{item['type']} — {item['time']}"
            ):
                st.markdown("**Original text**")
                st.text(item["text"])

                st.markdown("**Explanation**")
                st.markdown(item["result"])

                st.download_button(
                    "⬇️ Download result",
                    data=item["result"],
                    file_name=f"history_{index + 1}.txt",
                    mime="text/plain",
                    key=f"history_download_{index}"
                )


# =====================================================
# TAMIL TEXT ASSISTANT
# =====================================================

elif page == "Tamil Text Assistant":

    st.header("1. Add Your Tamil Text")

    method = st.radio(
        "Choose an input method",
        [
            "Type or Paste",
            "Speak in Tamil",
            "Upload a File or Image"
        ],
        horizontal=True,
        key="assistant_method"
    )

    # ---------------- VOICE ----------------

    if method == "Speak in Tamil":

        st.write(
            "Record your Tamil speech and convert it into text."
        )

        audio = st.audio_input(
            "🎙️ Record Tamil Voice",
            sample_rate=16000,
            key="assistant_audio"
        )

        if st.button("Convert Voice to Tamil Text"):

            api_key = get_api_key()

            if not api_key:
                st.error("Please configure SARVAM_API_KEY in Secrets.")

            elif audio is None:
                st.warning("Please record your voice first.")

            else:
                try:
                    with st.spinner("Converting voice to text..."):
                        transcript = transcribe_tamil_audio(
                            audio.getvalue(),
                            api_key
                        )

                    if transcript:
                        existing = st.session_state["tamil_text"].strip()

                        st.session_state["tamil_text"] = (
                            existing + "\n" + transcript
                            if existing else transcript
                        )

                        st.success("Tamil text recognized!")
                        st.rerun()

                    else:
                        st.warning("No speech was recognized.")

                except requests.exceptions.HTTPError as error:
                    details = (
                        error.response.text
                        if error.response is not None
                        else str(error)
                    )
                    st.error(f"Voice API error: {details}")

                except Exception as error:
                    st.error(f"Voice conversion failed: {error}")

    # ---------------- FILE OR IMAGE ----------------

    elif method == "Upload a File or Image":

        uploaded_file = st.file_uploader(
            "Upload a Tamil document or image",
            type=[
                "txt", "pdf", "docx",
                "png", "jpg", "jpeg"
            ],
            key="assistant_upload"
        )

        if uploaded_file is not None:

            if uploaded_file.name.lower().endswith(
                (".png", ".jpg", ".jpeg")
            ):
                st.image(
                    uploaded_file,
                    caption="Uploaded image",
                    use_container_width=True
                )

        if st.button("Extract Text from File or Image"):

            if uploaded_file is None:
                st.warning("Please select a file or image first.")

            else:
                try:
                    extracted = extract_text(uploaded_file)

                    st.session_state["tamil_text"] = extracted
                    st.success(
                        "Text extracted! Check and correct it below."
                    )
                    st.rerun()

                except Exception as error:
                    st.error(f"Text extraction failed: {error}")

    # ---------------- EDITABLE TEXT ----------------

    st.text_area(
        "Enter or edit Tamil text",
        key="tamil_text",
        height=220,
        placeholder="Type, speak, or extract text from a file/image..."
    )

    if st.button(
        "✨ Simplify Tamil and Explain",
        type="primary",
        key="simplify_text"
    ):

        api_key = get_api_key()
        source_text = st.session_state["tamil_text"].strip()

        if not api_key:
            st.error("Add SARVAM_API_KEY in Streamlit Cloud Secrets.")

        elif not source_text:
            st.warning("Please enter Tamil text first.")

        else:
            try:
                with st.spinner("Preparing the explanation..."):
                    result = simplify_tamil(
                        source_text,
                        api_key,
                        is_poem=False
                    )

                st.session_state["tamil_result"] = result
                save_history("Tamil Text", source_text, result)
                st.success("Explanation ready!")

            except Exception as error:
                st.error(f"Could not process text: {error}")

    if st.session_state["tamil_result"]:
        st.header("📘 Learning Result")
        st.markdown(st.session_state["tamil_result"])

        st.download_button(
            "⬇️ Download Explanation",
            data=st.session_state["tamil_result"],
            file_name="tamil_explanation.txt",
            mime="text/plain",
            key="text_download"
        )


# =====================================================
# POEM LEARNING
# =====================================================

elif page == "Poem Learning":

    st.header("📜 Ancient Tamil Poem Learning")

    st.write(
        "Type a poem or upload a poem document or image. "
        "The app will extract the text and explain it."
    )

    poem_method = st.radio(
        "Choose an input method",
        ["Type a Poem", "Upload a Poem File or Image"],
        horizontal=True,
        key="poem_method"
    )

    # ---------------- POEM UPLOAD ----------------

    if poem_method == "Upload a Poem File or Image":

        poem_file = st.file_uploader(
            "Upload poem file or image",
            type=[
                "txt", "pdf", "docx",
                "png", "jpg", "jpeg"
            ],
            key="poem_upload"
        )

        if poem_file is not None:

            if poem_file.name.lower().endswith(
                (".png", ".jpg", ".jpeg")
            ):
                st.image(
                    poem_file,
                    caption="Uploaded poem image",
                    use_container_width=True
                )

        if st.button("Load Poem from File or Image"):

            if poem_file is None:
                st.warning("Please upload a poem file or image.")

            else:
                try:
                    st.session_state["poem_text"] = extract_text(poem_file)
                    st.success(
                        "Poem text extracted! Check it below."
                    )
                    st.rerun()

                except Exception as error:
                    st.error(f"Could not read poem: {error}")

    # ---------------- POEM TEXT ----------------

    st.text_area(
        "Enter or edit your Ancient Tamil poem",
        key="poem_text",
        height=220,
        placeholder="Type or paste the poem here..."
    )

    if st.button(
        "📖 Explain This Poem",
        type="primary",
        key="explain_poem"
    ):

        api_key = get_api_key()
        poem = st.session_state["poem_text"].strip()

        if not api_key:
            st.error("Please configure SARVAM_API_KEY in Secrets.")

        elif not poem:
            st.warning("Please enter or upload a poem first.")

        else:
            try:
                with st.spinner("Explaining the poem..."):
                    result = simplify_tamil(
                        poem,
                        api_key,
                        is_poem=True
                    )

                st.session_state["poem_result"] = result
                save_history("Poem", poem, result)
                st.success("Poem explanation is ready!")

            except Exception as error:
                st.error(f"Could not explain the poem: {error}")

    if st.session_state["poem_result"]:
        st.header("📚 Poem Explanation")
        st.markdown(st.session_state["poem_result"])

        st.download_button(
            "⬇️ Download Poem Explanation",
            data=st.session_state["poem_result"],
            file_name="poem_explanation.txt",
            mime="text/plain",
            key="poem_download"
        )


# =====================================================
# FOOTER
# =====================================================

st.sidebar.caption(
    "History is saved for the current app session."
)

st.caption(
    "OCR may misread unclear or handwritten Tamil letters. "
    "Check the extracted text before requesting an explanation."
)









