#!/usr/bin/env python
# coding: utf-8

# In[1]:


"""
Resume Writer with Enhanced DOCX & PDF Export
Highlights Name, Sections, Bullets, and Achievements.
"""

import streamlit as st
import openai
import tempfile
import os
from io import BytesIO
from docx import Document
from docx.shared import Pt
from typing import Optional

# PDF generation
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

# --- Set OpenAI API key from environment ---
openai.api_key = os.environ.get("OPENAI_API_KEY")
if not openai.api_key:
    st.error("OpenAI API key not found. Set OPENAI_API_KEY in your environment.")
    st.stop()

# --- File parsing ---
try:
    from PyPDF2 import PdfReader
except ImportError:
    PdfReader = None

try:
    import docx2txt
except ImportError:
    docx2txt = None

try:
    import docx
except ImportError:
    docx = None

def extract_text_from_pdf(bytes_data: bytes) -> str:
    if PdfReader is None:
        return "(PyPDF2 not installed — cannot extract PDF text)"
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(bytes_data)
        tmp.flush()
        tmp_name = tmp.name
    try:
        reader = PdfReader(tmp_name)
        out = []
        for page in reader.pages:
            text = page.extract_text() or ""
            out.append(text)
        return "\n".join(out)
    finally:
        try: os.remove(tmp_name)
        except Exception: pass

def extract_text_from_docx(bytes_data: bytes) -> str:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
        tmp.write(bytes_data)
        tmp.flush()
        tmp_name = tmp.name
    try:
        if docx2txt is not None:
            return docx2txt.process(tmp_name) or ""
        elif docx is not None:
            doc = docx.Document(tmp_name)
            return "\n".join([p.text for p in doc.paragraphs])
        else:
            return "(docx parsing libs not installed)"
    finally:
        try: os.remove(tmp_name)
        except Exception: pass

def extract_text_from_txt(bytes_data: bytes) -> str:
    try:
        return bytes_data.decode('utf-8')
    except:
        try:
            return bytes_data.decode('latin-1')
        except:
            return ""

def extract_text(file) -> str:
    if file is None:
        return ""
    raw = file.read()
    name = getattr(file, 'name', '') or ''
    lower = name.lower()
    if lower.endswith('.pdf') or raw[:4] == b'%PDF':
        return extract_text_from_pdf(raw)
    if lower.endswith('.docx'):
        return extract_text_from_docx(raw)
    return extract_text_from_txt(raw)

# --- Build OpenAI prompt ---
def build_prompt(resume_text, job_text, tone="Professional"):
    """Builds a prompt for ATS-optimized, job-aligned résumé generation using GPT-3.5."""
    prompt = f"""
You are a professional résumé writer. Rewrite the candidate's résumé so it is tailored 
to the job description and optimized for Applicant Tracking Systems (ATS).

Guidelines:
- Focus on aligning résumé with the job description: emphasize relevant experience, skills, and achievements.
- Keep only relevant roles in detail. Summarize or remove unrelated/older experiences.
- Optimize for ATS: naturally include important keywords from the job description.
- Keep formatting simple and ATS-friendly: 
  * Use plain section headers (Summary, Experience, Education, Skills, Certifications).
  * Use bullet points for achievements.
  * Avoid tables, text boxes, or columns.
- Write in a {tone} tone.
- Limit the résumé to 1–2 pages maximum.
- **Output only the final résumé. Do not add any explanations, notes, or commentary.**
Candidate's current résumé:
{resume_text}

Job description:
{job_text}

Now return ONLY the rewritten résumé, nothing else:
"""
    return prompt

# --- OpenAI call ---
def call_openai_chat(prompt: str, model: str = "gpt-3.5-turbo") -> str:
    try:
        response = openai.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a professional résumé writer."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=2000
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"(OpenAI API error) {e}"

# --- DOCX generation ---
def create_docx(resume_text: str, filename="tailored_resume.docx") -> BytesIO:
    doc = Document()
    for line in resume_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        # Bold only section headers
        headers = ["name:", "skills:", "experience:", "education:", "certifications:"]
        if any(stripped.lower().startswith(h) for h in headers):
            p = doc.add_paragraph()
            run = p.add_run(stripped)
            run.bold = True
            run.font.size = Pt(12)
        else:
            # Keep the original line format
            doc.add_paragraph(stripped)
    buf = BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf

# --- PDF generation ---
def create_pdf(resume_text: str) -> BytesIO:
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=LETTER,
                            leftMargin=40, rightMargin=40, topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()
    story = []

    header_style = ParagraphStyle(
        name='Header',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        spaceAfter=6
    )
    normal_style = styles['Normal']

    headers = ["summary:", "skills:", "experience:", "education:", "certifications:"]

    for line in resume_text.splitlines():
        stripped = line.strip()
        if not stripped:
            story.append(Spacer(1, 4))
            continue
        if any(stripped.lower().startswith(h) for h in headers):
            story.append(Paragraph(stripped, header_style))
        else:
            story.append(Paragraph(stripped, normal_style))
    doc.build(story)
    buf.seek(0)
    return buf

# --- Streamlit UI ---
st.set_page_config(page_title="Resume Writer", layout="centered")
st.title("Resume Writer — Tailor your résumé")

# File upload
uploaded_resume = st.file_uploader("Upload your résumé (PDF/DOCX/TXT)", type=['pdf', 'docx', 'txt'])
uploaded_jd = st.file_uploader("Upload job description (PDF/DOCX/TXT)", type=['pdf', 'docx', 'txt'])

# Tone selection
custom_tone = st.selectbox(
    "Tone for résumé",
    ["professional and concise", "friendly and conversational", "formal", "creative"]
)

# Generate résumé
if st.button("Generate tailored résumé"):
    if not uploaded_resume or not uploaded_jd:
        st.error("Please upload both résumé and job description.")
    else:
        with st.spinner("Extracting files..."):
            resume_text = extract_text(uploaded_resume)
            job_text = extract_text(uploaded_jd)

        if not resume_text.strip() or not job_text.strip():
            st.error("Could not extract text from one of the files.")
        else:
            prompt = build_prompt(resume_text, job_text, tone=custom_tone)
            st.info("Generating tailored résumé...")
            output = call_openai_chat(prompt, model="gpt-3.5-turbo")

            if output.startswith("(OpenAI API error)"):
                st.error(output)
            else:
                st.success("Résumé generated!")
                
                # DOCX download
                docx_buf = create_docx(output)
                st.download_button("Download résumé as DOCX", docx_buf, file_name="tailored_resume.docx")
                
                # PDF download
                pdf_buf = create_pdf(output)
                st.download_button("Download résumé as PDF", pdf_buf, file_name="tailored_resume.pdf")
                
                # Preview
                st.subheader("Résumé Preview")
                st.code(output, language="text")


st.markdown('---')
st.markdown('**Privacy:** We dont hold any personal info.Uploaded files are sent to OpenAI only if you provide a key.')


# In[ ]:




