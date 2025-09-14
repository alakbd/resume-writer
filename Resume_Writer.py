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
from docx.shared import Pt, Inches
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx2pdf import convert

try:
    from PyPDF2 import PdfReader
except Exception:
    PdfReader = None

try:
    import docx2txt
except Exception:
    docx2txt = None

try:
    import docx
except Exception:
    docx = None

# --- Text Extraction ---
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
        except: pass

def extract_text_from_docx(bytes_data: bytes) -> str:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
        tmp.write(bytes_data)
        tmp.flush()
        tmp_name = tmp.name
    try:
        if docx2txt is not None:
            return docx2txt.process(tmp_name) or ""
        elif docx is not None:
            docx_doc = docx.Document(tmp_name)
            return "\n".join([p.text for p in docx_doc.paragraphs])
        else:
            return "(docx parsing libs not installed)"
    finally:
        try: os.remove(tmp_name)
        except: pass

def extract_text_from_txt(bytes_data: bytes) -> str:
    try: return bytes_data.decode('utf-8')
    except:
        try: return bytes_data.decode('latin-1')
        except: return ""

def extract_text(file) -> str:
    if file is None: return ""
    raw = file.read()
    name = getattr(file, 'name', '') or ''
    lower = name.lower()
    if lower.endswith('.pdf') or raw[:4] == b'%PDF':
        return extract_text_from_pdf(raw)
    if lower.endswith('.docx'):
        return extract_text_from_docx(raw)
    return extract_text_from_txt(raw)

# --- OpenAI ---
def build_prompt(resume_text: str, job_text: str, tone: str = 'professional and concise') -> str:
    system_instructions = (
        "You are a professional résumé writer. Tailor a résumé to a job description. Preserve facts. Use bullet points. Include metrics when possible."
    )
    prompt = f"{system_instructions}\n\nRÉSUMÉ:\n{resume_text}\n\nJOB DESCRIPTION:\n{job_text}\n\nTone: {tone}.\nReturn only the tailored résumé."
    return prompt

openai.api_key = os.environ.get("OPENAI_API_KEY")

def call_openai_chat(prompt: str, model: str = "gpt-3.5-turbo") -> str:
    try:
        response = openai.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=1200
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"(OpenAI API error) {e}"

# --- Name extraction ---
def extract_name(resume_text: str) -> str:
    lines = [l.strip() for l in resume_text.split("\n") if l.strip()]
    return lines[0] if lines else "Candidate Name"

# --- DOCX Generation with Highlights ---
def create_docx_resume(resume_text: str, name: str) -> BytesIO:
    doc = Document()

    # Name
    p_name = doc.add_paragraph()
    run_name = p_name.add_run(name)
    run_name.bold = True
    run_name.font.size = Pt(16)
    shading = OxmlElement('w:shd')
    shading.set(qn('w:fill'), 'FFFF00')
    run_name._r.get_or_add_rPr().append(shading)

    # Resume lines
    for line in resume_text.split("\n"):
        stripped = line.strip()
        if not stripped:
            doc.add_paragraph("")
            continue
        # Highlight section headers
        if stripped.lower().startswith(("skills:", "experience:", "education:", "certifications:", "summary:", "profile:")):
            p = doc.add_paragraph()
            run = p.add_run(stripped)
            run.bold = True
            shading = OxmlElement('w:shd')
            shading.set(qn('w:fill'), 'FFFF00')
            run._r.get_or_add_rPr().append(shading)
        # Bullet points
        elif stripped.startswith(("-", "•")):
            p = doc.add_paragraph(stripped, style='List Bullet')
            # Highlight achievements with numbers/metrics
            if any(c.isdigit() for c in stripped):
                p.runs[0].bold = True
        else:
            p = doc.add_paragraph(stripped)
            # Highlight lines with numbers/metrics
            if any(c.isdigit() for c in stripped):
                p.runs[0].bold = True

    buf = BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf

# --- DOCX → PDF ---
def docx_to_pdf(docx_buffer: BytesIO) -> BytesIO:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp_docx:
        tmp_docx.write(docx_buffer.getbuffer())
        tmp_docx.flush()
        tmp_docx_path = tmp_docx.name
    tmp_pdf_path = tmp_docx_path.replace(".docx", ".pdf")
    convert(tmp_docx_path, tmp_pdf_path)
    with open(tmp_pdf_path, "rb") as f:
        pdf_bytes = BytesIO(f.read())
    try: os.remove(tmp_docx_path)
    except: pass
    try: os.remove(tmp_pdf_path)
    except: pass
    pdf_bytes.seek(0)
    return pdf_bytes

# --- Streamlit UI ---
st.set_page_config(page_title='Resume Writer', layout='centered')
st.title('Resume Writer — Tailored Résumé with Highlights')

st.markdown("Upload résumé and job description. Sections, bullets, and achievements are highlighted. Download DOCX & PDF.")

api_key_input = os.environ.get('OPENAI_API_KEY', '')
if not api_key_input:
    st.error("Please setup Key it in the server environment.")

uploaded_resume = st.file_uploader('Upload résumé (PDF/DOCX/TXT)', type=['pdf','docx','txt'])
uploaded_jd = st.file_uploader('Upload job description (PDF/DOCX/TXT)', type=['pdf','docx','txt'])
tone = st.selectbox('Tone', ['professional and concise','friendly','formal','creative'])

if st.button('Generate tailored résumé'):
    if not uploaded_resume or not uploaded_jd:
        st.error('Please upload both a résumé and a job description.')
    else:
        with st.spinner('Extracting files...'):
            resume_text = extract_text(uploaded_resume)
            job_text = extract_text(uploaded_jd)

        prompt = build_prompt(resume_text, job_text, tone=custom_tone)

        st.info('Sending request to OpenAI...')
        with st.spinner('Generating tailored résumé...'):
            # ✅ Correct usage of call_openai_chat
            output = call_openai_chat(prompt, model="gpt-3.5-turbo")

        if output.startswith('(OpenAI API error)'):
            st.error(output)
        else:
            st.success('Done — tailored résumé generated.')
            # Show preview / download buttons as before
            st.download_button('Download résumé as .txt', output, file_name='tailored_resume.txt')
            st.subheader('Tailored résumé (preview)')
            st.code(output, language='text')


st.markdown('---')
st.markdown('**Privacy:** Uploaded files are sent to OpenAI only if you provide a key.')


# In[ ]:




