#!/usr/bin/env python
# coding: utf-8

# In[1]:


"""
Resume Writer with Enhanced DOCX & PDF Export
Highlights Name, Sections, Bullets, and Achievements.
"""

import streamlit as st
import openai
from docx import Document
from docx.shared import Pt
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import tempfile
import os
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
from reportlab.lib.units import inch


# -------- Build Prompt --------
def build_prompt(resume_text, job_text, tone="Professional"):
    """Prompt for ATS-optimized, job-aligned résumé using GPT-3.5 (no explanations)."""
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
- Output only the final résumé. Do not add explanations or commentary.

Candidate's current résumé:
{resume_text}

Job description:
{job_text}

Now return ONLY the rewritten résumé, nothing else:
"""
    return prompt


# -------- Call OpenAI GPT-3.5 --------
def call_openai_chat(prompt: str, api_key: str) -> str:
    """Call OpenAI GPT-3.5-turbo for résumé generation."""
    openai.api_key = api_key
    try:
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",   # locked to GPT-3.5
            messages=[{"role": "system", "content": prompt}],
            temperature=0.3,
            max_tokens=2000  # enough for 1–2 page résumé
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"(OpenAI API error) {e}"


# -------- Save as DOCX --------
def save_resume_docx(resume_text, filename="resume.docx"):
    """Save AI-generated resume into a styled Word document."""
    doc = Document()

    # Candidate Name Placeholder
    doc.add_paragraph("Candidate Name", style="Title")

    # Split sections by lines
    lines = resume_text.split("\n")
    current_section = None
    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Detect section headers
        if line.lower() in ["summary", "experience", "education", "skills", "certifications"]:
            current_section = line
            para = doc.add_paragraph(line.upper())
            run = para.runs[0]
            run.bold = True
            run.font.size = Pt(14)
            para.alignment = WD_PARAGRAPH_ALIGNMENT.LEFT
            doc.add_paragraph("")  # spacing
        else:
            if current_section == "experience" and line.startswith("-"):
                # Format as bullet point
                para = doc.add_paragraph(line[1:].strip(), style="List Bullet")
                para.runs[0].font.size = Pt(11)
            else:
                para = doc.add_paragraph(line)
                para.runs[0].font.size = Pt(11)

    doc.save(filename)
    return filename



# -------- Save as PDF --------
def save_resume_pdf(resume_text, filename="resume.pdf"):
    """Save AI-generated resume into a styled PDF document."""
    doc = SimpleDocTemplate(filename, pagesize=A4, rightMargin=50, leftMargin=50, topMargin=50, bottomMargin=50)
    styles = getSampleStyleSheet()
    story = []

    lines = resume_text.split("\n")
    current_section = None

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Section headers
        if line.lower() in ["summary", "experience", "education", "skills", "certifications"]:
            current_section = line
            story.append(Spacer(1, 0.2 * inch))
            story.append(Paragraph(f"<b>{line.upper()}</b>", styles["Heading2"]))
        else:
            if current_section == "experience" and line.startswith("-"):
                story.append(Paragraph("• " + line[1:].strip(), styles["Normal"]))
            else:
                story.append(Paragraph(line, styles["Normal"]))

    doc.build(story)
    return filename



# -------- Streamlit UI --------
def main():
    st.title("📄 AI Résumé Writer (GPT-3.5)")
    st.write("Upload your current résumé and a job description, and get a tailored, ATS-optimized résumé.")

    api_key_input = st.text_input("Enter your OpenAI API Key", type="password")

    resume_file = st.file_uploader("Upload your Résumé (TXT, DOCX)", type=["txt", "docx"])
    job_file = st.file_uploader("Upload Job Description (TXT, DOCX)", type=["txt", "docx"])

    tone = st.selectbox("Choose Résumé Tone", ["Professional", "Concise", "Impactful", "Leadership"])

    if st.button("Generate Tailored Résumé"):
        if not api_key_input:
            st.error("Please enter your OpenAI API Key.")
            return
        if not resume_file or not job_file:
            st.error("Please upload both résumé and job description.")
            return

        # Read uploaded files
        def read_file(file):
            if file.name.endswith(".txt"):
                return file.read().decode("utf-8")
            elif file.name.endswith(".docx"):
                doc = Document(file)
                return "\n".join([para.text for para in doc.paragraphs])
            return ""

        resume_text = read_file(resume_file)
        job_text = read_file(job_file)

        # Build prompt and call AI
        prompt = build_prompt(resume_text, job_text, tone=tone)
        output = call_openai_chat(prompt, api_key_input)

        st.subheader("✨ Tailored Résumé")
        st.text_area("Generated Résumé", output, height=400)

        # Save files
        with tempfile.TemporaryDirectory() as tmpdir:
            docx_file = os.path.join(tmpdir, "resume.docx")
            pdf_file = os.path.join(tmpdir, "resume.pdf")

            save_resume_docx(output, docx_file)
            save_resume_pdf(output, pdf_file)

            with open(docx_file, "rb") as f:
                st.download_button("📄 Download as Word (.docx)", f, file_name="resume.docx")

            with open(pdf_file, "rb") as f:
                st.download_button("📑 Download as PDF", f, file_name="resume.pdf")


if __name__ == "__main__":
    main()


st.markdown('---')
st.markdown('**Privacy:** We dont hold any personal info.Uploaded files are sent to OpenAI only if you provide a key.')


# In[ ]:




