import cloudinary
import cloudinary.uploader
import os
from dotenv import load_dotenv

load_dotenv()

# Set up Cloudinary configuration
CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
API_KEY = os.getenv("CLOUDINARY_API_KEY")
API_SECRET = os.getenv("CLOUDINARY_API_SECRET")

cloudinary.config(
    cloud_name=CLOUD_NAME,
    api_key=API_KEY,
    api_secret=API_SECRET,
)

def upload_to_cloudinary(file_path: str) -> str:
    result = cloudinary.uploader.upload(file_path, resource_type="auto")  # cloudinary will auto-detect the file type
    return result.get("secure_url")

