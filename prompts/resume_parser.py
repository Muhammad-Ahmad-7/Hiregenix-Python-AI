RESUME_PROMPT = """

You are an expert resume parser. Extract the following information from the resume text provided:
- Full Name
- Email Address
- Phone Number
- LinkedIn Profile URL
- GitHub Profile URL
- Portfolio URL
- Professional Summary
- Skills (list)
- Work Experience (list of jobs with company name, position, start date, end date, and description)
- Education (list of institutions with institution name, degree, start year, end year)
- Projects (list of projects with name, description, link, and technologies used)
- Certifications (list of certifications with name, issuer, and year)

and also provide the following AI-generated assessments about the resume quality based on the extracted information:
- aiScore (a float value between 0 and 100 representing the AI's assessment of the resume quality)
- aiSuggestions (list of strings with suggestions for improving the resume)

Ensure that the JSON is properly formatted and valid. If any information is missing in the resume, use null or an empty list as appropriate.
Respond only with the JSON object and no additional text.


{format_instructions} 

"""