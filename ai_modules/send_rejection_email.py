import os
import requests

from langchain.prompts import ChatPromptTemplate
from langchain.chat_models.base import init_chat_model
from pydantic import BaseModel, Field

from config.env import OPENAI_API_KEY
from utils.llm_call import get_llm_model

RESEND_API_KEY = os.getenv("RESEND_API_KEY")
EMAIL_FROM = os.getenv("EMAIL_FROM", "HireGenix <noreply@send.mail.hiregenix.dev>")


# ── Pydantic schema ────────────────────────────────────────────────────────────
class RejectionEmailContent(BaseModel):
    subject: str = Field(description="A respectful and concise rejection email subject line")
    body: str = Field(
        description=(
            "The full rejection email body written in multiple distinct paragraphs separated by "
            "blank lines. Be empathetic, respectful, and encouraging. "
            "Do NOT mention any attachments, documents, resumes, or portfolios."
        )
    )


# ── LLM rejection email generation ────────────────────────────────────────────
def generate_rejection_email_content(
    company_name: str,
    candidate_name: str,
    company_email: str,
    logger,
) -> RejectionEmailContent:
    try:
        model = get_llm_model("grok/gpt-oss-20b")
        structured_model = model.with_structured_output(RejectionEmailContent)

        prompt = ChatPromptTemplate.from_template(
            """
You are an HR manager writing a professional and empathetic rejection email on behalf of {company_name}.

Write a polished, respectful, and encouraging rejection email to the candidate.

Candidate name : {candidate_name}
Company name   : {company_name}
HR Email       : {company_email}

Requirements:
- Return a subject line and a body separately.
- The body MUST consist of at least 3 distinct paragraphs, each separated by a blank line.
  Paragraph 1 – thank the candidate warmly for their time and interest in {company_name}.
  Paragraph 2 – respectfully inform them that the team has decided to move forward with other candidates; keep it brief and do NOT give specific reasons.
  Paragraph 3 – encourage the candidate, wish them well in their job search, and invite them to apply for future openings. Include {company_email} as the point of contact.
- Use the candidate's name in the greeting.
- Mention the company name naturally within the body.
- Keep the tone empathetic, warm, and professional — never cold or dismissive.
- Do NOT mention any attachments, files, documents, resumes, or portfolios anywhere.
- Do NOT include lines such as "please find attached", "see attached", or any similar phrasing.
- Do not add a sign-off line — the HTML template will handle it.
"""
        )

        response = structured_model.invoke(
            prompt.format_messages(
                company_name=company_name,
                candidate_name=candidate_name,
                company_email=company_email,
            )
        )

        return response

    except Exception as e:
        logger.error(f"Error generating rejection email content: {e}")
        raise


# ── HTML wrapper ───────────────────────────────────────────────────────────────
def build_rejection_html_template(
    body_content: str,
    company_name: str,
    logo_url: str,
) -> str:
    paragraphs_html = "".join(
        f'<p style="color:#555;line-height:1.8;margin:0 0 16px 0;">{para.strip()}</p>'
        for para in body_content.strip().split("\n\n")
        if para.strip()
    )

    logo_block = (
        f'<img src="{logo_url}" alt="{company_name} logo" '
        f'style="max-height:50px;margin-bottom:20px;" />'
        if logo_url
        else ""
    )

    return f"""
    <html>
    <body style="font-family:Arial,sans-serif;background-color:#f4f4f4;padding:20px;">
        <table width="100%" cellpadding="0" cellspacing="0">
            <tr>
                <td align="center">
                    <table width="600" style="background-color:#ffffff;padding:30px;
                                              border-radius:8px;">
                        <tr>
                            <td>
                                {logo_block}
                                <h2 style="color:#333;margin-bottom:20px;">
                                    Update on Your Application at {company_name}
                                </h2>
                                {paragraphs_html}
                                <p style="margin-top:30px;">
                                    Best Regards,<br>
                                    <strong>HR Team — {company_name}</strong>
                                </p>
                                <hr style="margin-top:40px;">
                                <p style="font-size:12px;color:#999;">
                                    This is an automated email. Please do not reply directly.
                                </p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """


# ── Fallback (no LLM) ─────────────────────────────────────────────────────────
def fallback_rejection_email(
    candidate_name: str,
    company_name: str,
    company_email: str,
) -> RejectionEmailContent:
    return RejectionEmailContent(
        subject=f"Your Application at {company_name} — An Update",
        body=(
            f"Dear {candidate_name},\n\n"
            f"Thank you sincerely for taking the time to apply to {company_name} and for "
            f"the effort you put into the interview process. We truly appreciate your "
            f"interest in joining our team.\n\n"
            f"After careful consideration, we have decided to move forward with other "
            f"candidates whose experience more closely aligns with our current needs. "
            f"This was a difficult decision given the strong pool of applicants we received.\n\n"
            f"We genuinely encourage you to keep pursuing opportunities that match your "
            f"talents, and we warmly invite you to apply for future openings at {company_name}. "
            f"Should you have any questions, please feel free to reach out to us at {company_email}. "
            f"We wish you all the best in your job search and future endeavors."
        ),
    )


# ── Main entry point ───────────────────────────────────────────────────────────
def send_rejection_email(
    email: str,
    company_email: str,
    company_name: str,
    candidate_name: str,
    logo_url: str,
    logger,
) -> bool:
    try:
        logger.info(f"Preparing rejection email for {email}")

        if not RESEND_API_KEY:
            logger.error("RESEND_API_KEY is missing; skipping rejection email.")
            return False

        if not EMAIL_FROM:
            logger.error("EMAIL_FROM is missing; skipping rejection email.")
            return False

        # 1. Generate structured content via LLM
        try:
            email_content: RejectionEmailContent = generate_rejection_email_content(
                company_name=company_name,
                candidate_name=candidate_name,
                company_email=company_email,
                logger=logger,
            )
        except Exception as e:
            logger.warning(f"LLM failed ({e}), using fallback")
            email_content = fallback_rejection_email(
                candidate_name=candidate_name,
                company_name=company_name,
                company_email=company_email,
            )

        # 2. Wrap body in HTML template
        html_content = build_rejection_html_template(
            body_content=email_content.body,
            company_name=company_name,
            logo_url=logo_url,
        )

        # 3. Send via Resend
        payload = {
            "from": EMAIL_FROM,
            "to": [email],
            "subject": email_content.subject,
            "text": email_content.body,
            "html": html_content,
        }

        headers = {
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json",
        }

        response = requests.post(
            "https://api.resend.com/emails",
            json=payload,
            headers=headers,
            timeout=15,
        )

        if response.status_code >= 400:
            logger.error(f"Failed to send rejection email: {response.status_code} {response.text}")
            return False

        data = response.json()

        logger.info(f"Rejection email successfully sent to {email}. Resend ID: {data.get('id')}")
        return True

    except requests.RequestException as e:
        logger.error(f"Error sending rejection email: {e}")
        return False

    except Exception as e:
        logger.error(f"Error sending rejection email: {e}")
        return False
