
import streamlit as st
import requests
from pypdf import PdfReader
from docx import Document
from io import BytesIO

st.set_page_config(
    page_title="Ancient Tamil Learning Assistant",
    page_icon="📜",
    layout="wide"
)

st.title("📜 Ancient Tamil Learning Assistant")
st.write(
    "Understand Ancient Tamil through simple modern Tamil, "
    "word meanings, explanations, and voice input."
)


# ---------------- API KEY ----------------

def get_api_key():
    try:
        return st.secrets["SARVAM_API_KEY"]
    except Exception:
        return None


# ---------------- TAMIL VOICE INPUT ----------------

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


# ---------------- AI TAMIL EXPLANATION ----------------

def simplify_tamil(text, api_key):
    prompt = f"""
You are an expert Tamil literature teacher.

Explain the following Ancient or Classical Tamil text
in simple, clear modern Tamil.

Keep the original meaning accurate.
Use Tamil script, not Tanglish.
Do not invent meanings if the text is unclear.

Give the result using these headings:

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
                    "content": "You are a Tamil literature teacher."
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
    return result["choices"][0]["message"]["content"]


# ---------------- FILE TEXT EXTRACTION ----------------

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
                "Please paste the text manually."
            )

        return text

    elif filename.endswith(".docx"):
        doc = Document(BytesIO(file_bytes))

        return "\n".join(
            p.text for p in doc.paragraphs
            if p.text.strip()
        )

    else:
        raise ValueError(
            "Please upload a TXT, PDF, or DOCX file."
        )


# ---------------- SESSION STATE ----------------

if "tamil_input" not in st.session_state:
    st.session_state["tamil_input"] = ""

if "tamil_result" not in st.session_state:
    st.session_state["tamil_result"] = ""


# ---------------- INPUT METHOD ----------------

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


# ---------------- TYPE TEXT ----------------

if method == "Type or Paste":

    st.session_state["tamil_input"] = st.text_area(
        "Enter Ancient Tamil text",
        value=st.session_state["tamil_input"],
        height=200,
        key="typed_text",
        placeholder="Paste your Tamil poem or paragraph here..."
    )


# ---------------- VOICE INPUT ----------------

elif method == "Speak in Tamil":

    st.write(
        "Record your Tamil voice. "
        "The app will convert your speech into text."
    )

    audio = st.audio_input(
        "🎙️ Record Tamil Voice",
        sample_rate=16000
    )

    if st.button("Convert Voice to Tamil Text"):

        api_key = get_api_key()

        if not api_key:
            st.error(
                "Please add SARVAM_API_KEY in "
                "Streamlit Cloud → Settings → Secrets."
            )

        elif audio is None:
            st.warning("Please record your voice first.")

        else:
            try:
                with st.spinner(
                    "Converting your voice into Tamil text..."
                ):
                    transcript = transcribe_tamil_audio(
                        audio.getvalue(),
                        api_key
                    )

                if transcript:
                    st.session_state["tamil_input"] = transcript
                    st.success(
                        "Voice converted! Check the text below."
                    )
                else:
                    st.warning(
                        "No speech detected. Please record again."
                    )

            except requests.exceptions.HTTPError as e:
                details = (
                    e.response.text
                    if e.response is not None
                    else str(e)
                )
                st.error(f"Voice API error: {details}")

            except Exception as e:
                st.error(f"Voice conversion failed: {e}")

    st.session_state["tamil_input"] = st.text_area(
        "Recognized Tamil text — edit if needed",
        value=st.session_state["tamil_input"],
        height=200,
        key="voice_text_editor"
    )


# ---------------- UPLOAD FILE ----------------

else:

    uploaded_file = st.file_uploader(
        "Upload a Tamil text document",
        type=["txt", "pdf", "docx"]
    )

    if uploaded_file is not None:

        if st.button("Extract Text from File"):

            try:
                extracted = extract_text(uploaded_file)

                st.session_state["tamil_input"] = extracted
                st.success("Text extracted successfully.")

            except Exception as e:
                st.error(f"File reading failed: {e}")

    st.session_state["tamil_input"] = st.text_area(
        "Extracted Tamil text — edit if needed",
        value=st.session_state["tamil_input"],
        height=200,
        key="file_text_editor"
    )


# ---------------- SIMPLIFY BUTTON ----------------

st.divider()
st.header("2. Simplify Ancient Tamil")

if st.button("✨ Simplify Tamil and Explain", type="primary"):

    api_key = get_api_key()
    text = st.session_state["tamil_input"].strip()

    if not api_key:
        st.error(
            "Add SARVAM_API_KEY in Streamlit Cloud Secrets."
        )

    elif not text:
        st.warning(
            "Please type, speak, or upload Tamil text first."
        )

    else:
        try:
            with st.spinner(
                "Preparing your Tamil explanation..."
            ):
                st.session_state["tamil_result"] = simplify_tamil(
                    text,
                    api_key
                )

        except requests.exceptions.Timeout:
            st.error(
                "Request timed out. Please try a shorter paragraph."
            )

        except requests.exceptions.HTTPError as e:
            details = (
                e.response.text
                if e.response is not None
                else str(e)
            )
            st.error(f"Sarvam API error: {details}")

        except Exception as e:
            st.error(f"Something went wrong: {e}")


# ---------------- DISPLAY RESULT ----------------

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

st.caption(
    "AI-generated explanations may contain mistakes. "
    "Verify important literary meanings with a Tamil teacher."
)







