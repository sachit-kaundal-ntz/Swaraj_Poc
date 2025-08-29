# import vertexai
# from vertexai.generative_models import GenerativeModel


# vertexai.init(
#     project="swaraj-datalake-dev-863225",
#     location="us-central1"
# )
# model = GenerativeModel("gemini-2.5-flash")
# response = model.generate_content("What is the capital of India")
# print(response.text)


import os
from google.oauth2 import service_account
import vertexai
from vertexai.generative_models import GenerativeModel, Part
import mimetypes


SA_PATH = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", r"C:\Users\50013525\Documents\sbc_phase_1\gemini_key.json")
SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]
creds = service_account.Credentials.from_service_account_file(SA_PATH, scopes = SCOPES)

def make_part(path:str) -> Part:
    mime,_ = mimetypes.guess_type(path)
    if not mime: 
        mime = "application/octet-stream"
    with open(path,"rb") as f:
        data =f.read()
    return Part.from_data(mime_type=mime, data=data)

vertexai.init(
    project="swaraj-datalake-dev-863225",
    location="us-central1",
    credentials=creds
)
model = GenerativeModel("gemini-2.5-flash")
img_part = make_part(r"C:\Users\50013525\Documents\sbc_phase_1\TestImage\P50011489B_001_p0.png")

response = model.generate_content(["EXTRACT ALL THE DIMENSIONS FROM THIS DRAWING", img_part])
print(response.text)