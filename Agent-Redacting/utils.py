import os
import requests
from dotenv import load_dotenv
import json
import base64
from PIL import Image
from io import BytesIO
import io

load_dotenv()


def pp(obj):
    print(json.dumps(obj, indent=4))


def show_image(base_64_image):
    image_data = base64.b64decode(base_64_image)
    image = Image.open(BytesIO(image_data))
    image.show()


def calculate_image_dimensions(base_64_image):
    image_data = base64.b64decode(base_64_image)
    image = Image.open(io.BytesIO(image_data))
    return image.size


def create_response(**kwargs):
    url = "https://api.openai.com/v1/responses"
    headers = {
        "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}",
        "Openai-Organization": os.getenv("OPENAI_ORG"),
        "Content-Type": "application/json",
        "Openai-beta": "responses=v1",
    }
    response = requests.post(url, headers=headers, json=kwargs)
    if response.status_code != 200:
        print("Error:", response.status_code, response.text)
    return response.json()
