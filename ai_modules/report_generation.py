from config.db import report_collection, question_result_collection, candidate_collection, interview_collection
from bson import ObjectId

from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    ListFlowable, ListItem, HRFlowable, Flowable
)
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from sqlalchemy import null

from bson import ObjectId
import datetime

from utils.cloudinary_upload import upload_report_to_cloudinary


# -------------------------------------------------
# PROGRESS BAR CLASS
# -------------------------------------------------
class ProgressBar(Flowable):
    def __init__(self, width, height, percent, bar_color=colors.HexColor("#1D4ED8")):
        super().__init__()
        self.width = width
        self.height = height
        self.percent = percent
        self.bar_color = bar_color

    def draw(self):
        # Outline
        self.canv.setStrokeColor(colors.HexColor("#D1D5DB"))
        self.canv.rect(0, 0, self.width, self.height, stroke=1, fill=0)
        # Filled bar
        fill_width = self.width * (self.percent / 100)
        self.canv.setFillColor(self.bar_color)
        self.canv.rect(0, 0, fill_width, self.height, stroke=0, fill=1)


# -------------------------------------------------
# REPORT GENERATOR FUNCTION
# -------------------------------------------------
def generate_interview_report(candidate_info, interview_data, question_results, filename="Interview_Report.pdf"):
    """
    Generates a PDF report for a candidate interview.

    :param interview_data: dict, overall interview data
    :param question_results: list of dict, question-level analysis
    :param filename: str, output PDF filename
    """

    doc = SimpleDocTemplate(
        filename,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=50,
        bottomMargin=30
    )

    elements = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "TitleStyle",
        parent=styles["Heading1"],
        fontSize=20,
        textColor=colors.HexColor("#111827"),
        spaceAfter=6
    )

    section_style = ParagraphStyle(
        "SectionStyle",
        parent=styles["Heading2"],
        fontSize=13,
        textColor=colors.HexColor("#1D4ED8"),
        spaceBefore=12,
        spaceAfter=6
    )

    normal_style = styles["Normal"]

    # -------------------------------------------------
    # HEADER
    # -------------------------------------------------
    elements.append(Paragraph("<b>HireGenix</b> AI Hiring Intelligence Report", title_style))
    elements.append(Spacer(1, 0.25 * inch))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#D1D5DB")))
    elements.append(Spacer(1, 0.25 * inch))

    elements.append(Paragraph("Candidate Information", section_style))
    candidate_table = Table([[k.capitalize() + ":", v] for k, v in candidate_info.items()], colWidths=[2.2*inch, 3.3*inch])
    candidate_table.setStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F9FAFB")),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E5E7EB")),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ])
    elements.append(candidate_table)
    elements.append(Spacer(1, 0.3*inch))

    # -------------------------------------------------
    # EXECUTIVE SUMMARY WITH PROGRESS BARS
    # -------------------------------------------------
    elements.append(Paragraph("Executive Summary", section_style))

    # Helper to create score rows
    def make_score_row(label, score):
        return [
            Paragraph(label, normal_style),
            Paragraph(f"{score}%", normal_style),
            ProgressBar(width=2.5*inch, height=10, percent=score)
        ]

    score_data = [
        make_score_row("Overall Score", interview_data.get("overallInterviewScore", 0))
    ]
    for key, label in [("contentScore","Content"),("communicationScore","Communication"),
                       ("fluencyScore","Fluency"),("confidenceScore","Confidence")]:
        score_data.append(make_score_row(label, interview_data.get(key, 0)))

    score_table = Table(score_data, colWidths=[1.5*inch, 0.6*inch, 2.7*inch])
    score_table.setStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 0), (1, -1), "CENTER"),
        ("BOX", (0, 0), (-1, -1), 0.25, colors.HexColor("#E5E7EB")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E5E7EB")),
    ])
    elements.append(score_table)
    elements.append(Spacer(1, 0.25*inch))

    # Strengths
    elements.append(Paragraph("Key Strengths", section_style))
    elements.append(ListFlowable([ListItem(Paragraph(s, normal_style)) for s in interview_data.get("topStrengths", [])], bulletType='bullet'))
    elements.append(Spacer(1, 0.15*inch))

    # Weaknesses
    elements.append(Paragraph("Risk Indicators", section_style))
    elements.append(ListFlowable([ListItem(Paragraph(w, normal_style)) for w in interview_data.get("topWeaknesses", [])], bulletType='bullet'))
    elements.append(Spacer(1, 0.2*inch))

    # Common Missing Concepts
    elements.append(Paragraph("Common Missing Concepts", section_style))
    elements.append(ListFlowable([ListItem(Paragraph(m, normal_style)) for m in interview_data.get("commonMissingConcepts", [])], bulletType='bullet'))
    elements.append(Spacer(1, 0.2*inch))

    # Interview Summary
    elements.append(Paragraph("Interview Summary", section_style))
    elements.append(Paragraph(interview_data.get("interviewSummary", ""), normal_style))
    elements.append(Spacer(1, 0.3*inch))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#D1D5DB")))
    elements.append(Spacer(1, 0.25*inch))

    # -------------------------------------------------
    # QUESTION LEVEL EVALUATION
    # -------------------------------------------------
    elements.append(Paragraph("Question-Level Evaluation", section_style))

    for q in question_results:
        elements.append(Spacer(1, 0.15*inch))
        elements.append(Paragraph(f"<h3><b>{q.get('questionId', '')} {q.get('questionText', '')}</b></h3>", normal_style))
        elements.append(Spacer(1, 0.1*inch))

        # Scores from LLM Analysis if available
        if q.get("lLMAnalysis") == None:
            print(f"No LLM analysis available for question: {q.get('questionId', 'N/A')}")
            continue  # Skip if no scores available
        llm_scores = q.get("lLMAnalysis", {}).get("scores", {})
        q_score_data = [make_score_row("Overall", llm_scores.get("overallScore", 0))]
        for key, label in [("contentScore","Content"),("communicationScore","Communication"),
                        ("fluencyScore","Fluency"),("confidenceScore","Confidence")]:
            q_score_data.append(make_score_row(label, llm_scores.get(key, 0)))

        q_table = Table(q_score_data, colWidths=[1.5*inch,0.6*inch,2.7*inch])
        q_table.setStyle([
            ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
            ("ALIGN",(1,0),(1,-1),"CENTER"),
            ("BOX",(0,0),(-1,-1),0.25,colors.HexColor("#E5E7EB")),
            ("INNERGRID",(0,0),(-1,-1),0.25,colors.HexColor("#E5E7EB")),
        ])
        elements.append(q_table)
        elements.append(Spacer(1,0.12*inch))

        # Strengths
        elements.append(Paragraph("Strengths", section_style))
        strengths = q.get("lLMAnalysis", {}).get("insights", {}).get("strengths", [])
        elements.append(ListFlowable([ListItem(Paragraph(s, normal_style)) for s in strengths], bulletType='bullet'))
        elements.append(Spacer(1,0.12*inch))

        # Gaps / Weaknesses
        elements.append(Paragraph("Gaps Identified", section_style))
        weaknesses = q.get("lLMAnalysis", {}).get("insights", {}).get("weaknesses", [])
        elements.append(ListFlowable([ListItem(Paragraph(w, normal_style)) for w in weaknesses], bulletType='bullet'))
        elements.append(Spacer(1,0.25*inch))
        elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#E5E7EB")))

    # -------------------------------------------------
    # BUILD PDF
    # -------------------------------------------------
    doc.build(elements)
    print(f"{filename} generated successfully.")





def report_generation_pipeline(interview_id, candidate_id):
    # Placeholder for report generation logic
    # Fetch necessary data using question_result_id, perform processing, and generate report
    # Return the result or status of the report generation
    
    try:
        print(f"Starting report generation for Interview ID: {interview_id}")
        report_doc = report_collection.find_one({"interviewId": ObjectId(interview_id)})
        if not report_doc:
            print(f"Report document not found for ID: {interview_id}")
            return None
        question_results = list(question_result_collection.find({"interviewId": ObjectId(interview_id)}))
        if not question_results:
            print(f"No question results found for Interview ID: {interview_id}")
            return None
        
        candidate_doc = candidate_collection.find_one({"_id": ObjectId(candidate_id)})  # Fetch candidate details if needed
        if not candidate_doc:
            print(f"Candidate document not found for ID: {candidate_id}")
            return None
        # print(f"Fetched interview document and question results for Interview ID: {interview_id}")
        # print(f"Report Doc: {report_doc}")
        # print(f"Question Docs: {question_results}")
        print(f"Candidate Doc: {candidate_doc}")
        
        name=candidate_doc['fullName']
        candidate_information = {
            "name":  candidate_doc.get("fullName", "N/A"),
            "Contact Number": candidate_doc.get("contactNumber", "N/A"),
            "Location": f"{candidate_doc.get('city', 'N/A')}, {candidate_doc.get('country', 'N/A')}",
        }
        
        filename=f"Interview_Report_{interview_id}.pdf"
        
        generate_interview_report(candidate_information, report_doc, question_results, filename=filename)
        print(f"Report generation completed for Interview ID: {interview_id}")
        uploaded_url = upload_report_to_cloudinary(filename)
        if uploaded_url:
            print(f"Uploaded report URL: {uploaded_url}")
        else:
            print("Failed to upload report to Cloudinary.")
        
        doc = report_collection.find_one_and_update(
            {"_id": report_doc["_id"]},
            {"$set": {"pdfUrl": uploaded_url, "updatedAt": datetime.datetime.now()}},
            return_document=True
        )
        
        interview_collection.find_one_and_update(
            {"_id": ObjectId(interview_id)},
            {"$set": {"status": "completed", "updatedAt": datetime.datetime.now()}},
        )
        
        if not doc:
            print(f"Failed to update report document with PDF URL for Interview ID: {interview_id}")
            return None
        
        print(f"Report document updated with PDF URL for Interview ID: {interview_id}")
        return doc
    except Exception as e:
        print(f"Error during report generation: {e}")
        return False
    
    return True  # Simulating successful report generation