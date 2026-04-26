import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from langchain.prompts import ChatPromptTemplate
from langchain.chat_models.base import init_chat_model
from pydantic import BaseModel, Field

from config.env import OPENAI_API_KEY, EMAIL_HOST, EMAIL_PORT, EMAIL_USER, EMAIL_PASS


# ── Pydantic schema for structured LLM output ──────────────────────────────────
class EmailContent(BaseModel):
    subject: str = Field(description="A concise, compelling email subject line")
    body: str = Field(
        description=(
            "The full email body written in multiple distinct paragraphs separated by "
            "blank lines. Do NOT mention any attachments, documents, resumes, portfolios, "
            "or anything that implies a file is being sent or expected."
        )
    )


# ── LLM email generation ────────────────────────────────────────────────────────
def generate_email_content(
    query: str,
    company_name: str,
    candidate_name: str,
    company_email: str,
    logger,
) -> EmailContent:
    try:
        model = init_chat_model(
            model_provider="google_genai",
            model="gemini-2.5-flash",
            api_key=OPENAI_API_KEY,
        )

        # Bind the Pydantic schema so the model returns structured output
        structured_model = model.with_structured_output(EmailContent)

        prompt = ChatPromptTemplate.from_template(
            """
You are an HR manager writing a professional hiring email on behalf of {company_name}.

Write a polished, friendly, and professional hiring email to the candidate.

Context / Role details:
{query}

Candidate name  : {candidate_name}
Company name    : {company_name}
HR Email: {company_email}

Requirements:
- Return a subject line and a body separately.
- The body MUST consist of at least 3 distinct paragraphs, each separated by a blank line.
  Paragraph 1 – warm opening / introduction of the company.
  Paragraph 2 – describe the opportunity and why the candidate is a great fit.
  Paragraph 3 – clear call to action (e.g., schedule a call, reply to confirm interest).
  Optional Paragraph 4 – closing / sign-off note.
- Use the candidate's name in the greeting.
- Mention the company name naturally within the body.
- Include the HR email in the call-to-action paragraph.
- Do NOT mention any attachments, files, documents, resumes, or portfolios anywhere.
- Do NOT include lines such as "please find attached", "see attached", "attached herewith",
  or any similar phrasing that implies something is being attached or sent as a file.
- Keep the tone warm yet professional.
- Do not add a sign-off line — the HTML template will handle it.
"""
        )

        response = structured_model.invoke(
            prompt.format_messages(
                query=query,
                company_name=company_name,
                candidate_name=candidate_name,
                company_email=company_email,
            )
        )

        return response  # Already an EmailContent instance

    except Exception as e:
        logger.error(f"Error generating email content: {e}")
        raise


# ── HTML wrapper ────────────────────────────────────────────────────────────────
def build_html_template(
    body_content: str,
    company_name: str,
    logo_url: str,
) -> str:
    # Convert blank-line-separated paragraphs → <p> tags
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
                                    Exciting Opportunity at {company_name}
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


# ── Fallback (no LLM) ───────────────────────────────────────────────────────────
def fallback_email(
    query: str,
    candidate_name: str,
    company_name: str,
    company_email: str,
    contact_number: str,
) -> EmailContent:
    return EmailContent(
        subject=f"Exciting Opportunity at {company_name}",
        body=(
            f"Dear {candidate_name},\n\n"
            f"We hope this message finds you well. My name is from the HR team at "
            f"{company_name}, and we came across your profile while searching for "
            f"talented professionals in our domain.\n\n"
            f"We have been impressed by your background and believe you could be a "
            f"fantastic fit for an opening we currently have: {query}. "
            f"This is a great opportunity to grow your career with a dynamic team.\n\n"
            f"We would love to connect and tell you more. Please feel free to reach "
            f"us at {company_email} or simply reply to this email to schedule a "
            f"quick introductory call at your convenience."
        ),
    )


# ── Main entry point ────────────────────────────────────────────────────────────
def send_hiring_email(
    email: str,
    query: str,
    company_email: str,
    company_name: str,
    candidate_name: str,
    logo_url: str,
    contact_number: str,
    logger,
) -> bool:
    try:
        logger.info(f"Preparing hiring email for {email}")

        # 1. Generate structured content via LLM
        try:
            email_content: EmailContent = generate_email_content(
                query=query,
                company_name=company_name,
                candidate_name=candidate_name,
                company_email=company_email,
                logger=logger,
            )
        except Exception as e:
            logger.warning(f"LLM failed ({e}), using fallback")
            email_content = fallback_email(
                query=query,
                candidate_name=candidate_name,
                company_name=company_name,
                contact_number=contact_number,
            )

        # 2. Wrap body in HTML template
        html_content = build_html_template(
            body_content=email_content.body,
            company_name=company_name,
            logo_url=logo_url,
        )

        # 3. Build MIME message using LLM-generated subject
        msg = MIMEMultipart("alternative")
        msg["Subject"] = email_content.subject   # ← from LLM, not hardcoded
        msg["From"] = EMAIL_USER
        msg["To"] = email

        msg.attach(MIMEText(html_content, "html"))

        # 4. Send via SMTP
        with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT) as server:
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASS)
            server.sendmail(EMAIL_USER, email, msg.as_string())

        logger.info(f"Email successfully sent to {email}")
        return True

    except Exception as e:
        logger.error(f"Error sending hiring email: {e}")
        return False