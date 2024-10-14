from fastapi import FastAPI, File, UploadFile, Form, Request, HTTPException 
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
import base64
import io
from PIL import Image
from dotenv import load_dotenv
import os
import logging
from groq import Groq

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY is not set in the .env file")

# Function to encode image to base64
def encode_image(image_content):
    return base64.b64encode(image_content).decode('utf-8')

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/upload_and_query")
async def upload_and_query(image: UploadFile = File(...), query: str = Form(...)):
    try:
        # Read and encode the image
        image_content = await image.read()
        if not image_content:
            raise HTTPException(status_code=400, detail="Empty file")
        
        encoded_image = encode_image(image_content)

        # Validate image format
        try:
            img = Image.open(io.BytesIO(image_content))
            img.verify()
        except Exception as e:
            logger.error(f"Invalid image format: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Invalid image format: {str(e)}")

        # Prepare the messages for Groq API
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": query},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded_image}"}}
                ]
            }
        ]

        # Function to make API request
        def make_api_request(model):
            client = Groq(api_key=GROQ_API_KEY)
            try:
                chat_completion = client.chat.completions.create(
                    messages=messages,
                    model=model,
                )
                return chat_completion
            except Exception as e:
                logger.error(f"Error from {model} API: {str(e)}")
                return {"error": str(e)}

        # Make requests to both models
        llama_response = make_api_request("llama-3.2-11b-vision-preview")
        llava_response = make_api_request("llava-v1.5-7b-4096-preview")

        # Process responses
        responses = {}
        for model, response in [("llama", llama_response), ("llava", llava_response)]:
            if "error" not in response:
                answer = response.choices[0].message.content
                logger.info(f"Processed response from {model} API: {answer[:100]}...")
                responses[model] = answer
            else:
                logger.error(f"Error from {model} API: {response['error']}")
                responses[model] = f"Error from {model} API: {response['error']}"

        return JSONResponse(status_code=200, content=responses)

    except HTTPException as he:
        logger.error(f"HTTP Exception: {str(he)}")
        raise he
    except Exception as e:
        logger.error(f"An unexpected error occurred: {str(e)}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
