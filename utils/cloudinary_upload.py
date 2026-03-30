import cloudinary
import cloudinary.uploader
import os
from config.env import CLOUDNAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET

print(cloudinary.__file__)

cloudinary.config(
    cloud_name = CLOUDNAME,
    api_key = CLOUDINARY_API_KEY,
    api_secret = CLOUDINARY_API_SECRET,
    secure = True
)

def upload_report_to_cloudinary(file_path):
    """
    Uploads a file to Cloudinary and returns the secure URL.
    """
    if not os.path.isfile(file_path):
        print(f"File not found: {file_path}")
        return None

    try:
        response = cloudinary.uploader.upload(file_path, resource_type="raw")
        print("Upload response:", response)
        return response.get("secure_url")
    except Exception as e:
        print(f"Error uploading {file_path} to Cloudinary: {e}")
        return None

# file_path = "Interview_Report_69a7f2b7472d6d3eb2db06fc.pdf"
# uploaded_url = upload_report_to_cloudinary(file_path)
# print("Uploaded PDF URL:", uploaded_url)