
import streamlit as st
import requests
from io import BytesIO
from pypdf import PdfReader
from docx import Document

# ==================================================
# PAGE SETTINGS
# ==================================================

st.set_page_config(
    page_title="Ancient Tamil Learning Assistant",
    page_icon="📜",
    layout="wide"
)

st.title("📜 Ancient Tamil Learning Assistant")
st.write(
    "Speak or enter Ancient Tamil text and understand it "
    "in simple modern Tamil."
)


# ==================================================
# SESSION STATE
# ==================================================

if "tamil_input" not in st.session_state:
    st.session_state["tamil_input"] = ""

if "tamil_result" not in st.session_state:
    st.session_state["tamil_result"] = ""


# ==================================================
# API KEY
# ==================================================

def get_api_key():
    try:
        return st.secrets["SARVAM_API_KEY"]
    except Exception:
        return None


# ==================================================
# VOICE TO TAMIL TEXT
# ==================================================

def transcribe_tamil_audio(audio_bytes, api_key):

    response = requests.post(
        "https://api.sarvam.ai/speech-to-text",
        headers={
            "api-subscription-key": api_key
        },
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

    result = response.json()
    return result.get("transcript", "").strip()


# ==================================================
# ANCIENT TAMIL EXPLANATION
# ==================================================

def simplify_tamil(text, api_key):

    prompt = f"""
You are an expert Tamil language and literature teacher.

Explain the following Ancient or Classical Tamil text
in clear, simple modern Tamil.

Instructions:
- Use Tamil script, not Tanglish.
- Preserve the original meaning.
- Explain difficult and old Tamil words.
- Explain each line clearly when possible.
- Do not invent meanings if the text is unclear.
- Make the explanation suitable for students.

Use these headings:

1. எளிய நவீன தமிழ்
2. கடினமான சொற்களின் பொருள்
3. வரி வாரியான விளக்கம்
4. மொத்தக் கருத்து
5. சுருக்கம்
6. கற்றுக்கொள்ள வேண்டிய கருத்து

Tamil text:
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
                        "Answer in simple modern Tamil."
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.2,
            "max_tokens": 2500
        },
        timeout=180
    )

    response.raise_for_status()

    result = response.json()
    return result["choices"][0]["message"]["content"].strip()


# ==================================================
# FILE EXTRACTION
# ==================================================

def extract_text(uploaded_file):

    filename = uploaded_file.name.lower()
    file_bytes = uploaded_file.getvalue()

    if filename.endswith(".txt"):

        return file_bytes.decode("utf-8-sig")

    elif filename.endswith(".pdf"):

        pdf = PdfReader(BytesIO(file_bytes))

        text = "\n".join(
            page.extract_text() or ""
            for page in pdf.pages
        ).strip()

        if not text:
            raise ValueError(
                "No selectable text found in this PDF. "
                "Please copy or type the Tamil text manually."
            )

        return text

    elif filename.endswith(".docx"):

        document = Document(BytesIO(file_bytes))

        paragraphs = [
            paragraph.text
            for paragraph in document.paragraphs
            if paragraph.text.strip()
        ]

        return "\n".join(paragraphs)

    raise ValueError("Please upload a TXT, PDF, or DOCX file.")


# ==================================================
# CHOOSE INPUT METHOD
# ==================================================

st.header("1. Add Your Tamil Text")

method = st.radio(
    "Choose an input method",
    [
        "Type or Paste",
        "Speak in Tamil",
        "Upload a File"
    ],
    horizontal=True
)


# ==================================================
# VOICE RECORDING
# ==================================================

if method == "Speak in Tamil":

    st.write(
        "Record your Tamil voice and convert it into text. "
        "You can make additional recordings to add more text."
    )

    audio = st.audio_input(
        "🎙️ Record Tamil Voice",
        sample_rate=16000,
        key="tamil_audio"
    )

    if st.button("Convert Voice to Tamil Text"):

        api_key = get_api_key()

        if not api_key:

            st.error(
                "API key missing. Add SARVAM_API_KEY in "
                "Streamlit Cloud → Settings → Secrets."
            )

        elif audio is None:

            st.warning("Please record your voice first.")

        else:

            try:

                with st.spinner(
                    "Converting your Tamil voice into text..."
                ):

                    transcript = transcribe_tamil_audio(
                        audio.getvalue(),
                        api_key
                    )

                if transcript:

                    # Append recognized speech to the existing text.
                    previous_text = st.session_state["tamil_input"].strip()

                    if previous_text:
                        st.session_state["tamil_input"] = (
                            previous_text + "\n" + transcript
                        )
                    else:
                        st.session_state["tamil_input"] = transcript

                    st.session_state["tamil_result"] = ""

                    st.success(
                        "Tamil text recognized! Check the text box below."
                    )

                else:

                    st.warning(
                        "No text was recognized. Please try again."
                    )

            except requests.exceptions.HTTPError as error:

                details = (
                    error.response.text
                    if error.response is not None
                    else str(error)
                )

                st.error(
                    "Voice conversion failed. API response: "
                    + details
                )

            except requests.exceptions.Timeout:

                st.error(
                    "The request timed out. Please try again."
                )

            except Exception as error:

                st.error(f"Voice conversion failed: {error}")


# ==================================================
# FILE UPLOAD
# ==================================================

elif method == "Upload a File":

    uploaded_file = st.file_uploader(
        "Upload a TXT, PDF, or DOCX file",
        type=["txt", "pdf", "docx"]
    )

    if st.button("Extract Text from File"):

        if uploaded_file is None:

            st.warning("Please select a file first.")

        else:

            try:

                extracted_text = extract_text(uploaded_file)

                st.session_state["tamil_input"] = extracted_text
                st.session_state["tamil_result"] = ""

                st.success("Text extracted successfully!")

            except Exception as error:

                st.error(f"File reading failed: {error}")


# ==================================================
# ONE SHARED EDITABLE TEXT BOX
# ==================================================

st.subheader("Recognized or Entered Tamil Text")

st.text_area(
    "Edit your Tamil text here",
    key="tamil_input",
    height=220,
    placeholder=(
        "Type Tamil here, speak using the microphone, "
        "or extract text from a file..."
    )
)


# ==================================================
# SIMPLIFY BUTTON
# ==================================================

st.divider()

st.header("2. Simplify Ancient Tamil")

if st.button(
    "✨ Simplify Tamil and Explain",
    type="primary"
):

    api_key = get_api_key()
    source_text = st.session_state["tamil_input"].strip()

    if not api_key:

        st.error(
            "Add SARVAM_API_KEY in "
            "Streamlit Cloud → Settings → Secrets."
        )

    elif not source_text:

        st.warning(
            "Please enter, record, or upload Tamil text first."
        )

    else:

        try:

            with st.spinner(
                "Preparing your modern Tamil explanation..."
            ):

                result = simplify_tamil(source_text, api_key)

            st.session_state["tamil_result"] = result

        except requests.exceptions.Timeout:

            st.error(
                "The request took too long. Try a shorter paragraph."
            )

        except requests.exceptions.HTTPError as error:

            details = (
                error.response.text
                if error.response is not None
                else str(error)
            )

            st.error(f"Sarvam API error: {details}")

        except Exception as error:

            st.error(f"Something went wrong: {error}")


# ==================================================
# DISPLAY RESULT
# ==================================================

if st.session_state["tamil_result"]:

    st.divider()

    st.header("📚 Your Learning Result")

    st.markdown(st.session_state["tamil_result"])

    st.download_button(
        "⬇️ Download Explanation",
        data=st.session_state["tamil_result"],
        file_name="tamil_explanation.txt",
        mime="text/plain"
    )


# ==================================================
# FOOTER
# ==================================================

st.caption(
    "AI explanations may contain mistakes, especially for rare "
    "classical Tamil words. Verify important meanings with a "
    "Tamil teacher or trusted reference."
)








