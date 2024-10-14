import os
import sys
import io
import base64
import requests
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
from dotenv import load_dotenv
from PIL import Image, UnidentifiedImageError  # Updated import for better error handling
from groq import Groq

# Load environment variables from .env
load_dotenv()

app = Flask(__name__)

# Retrieve API keys and credentials
twilio_account_sid = os.getenv("TWILIO_ACCOUNT_SID")
twilio_auth_token = os.getenv("TWILIO_AUTH_TOKEN")
groq_api_key = os.getenv("GROQ_API_KEY")

# Initialize Twilio and Groq clients
twilio_client = Client(twilio_account_sid, twilio_auth_token)
client_groq = Groq(api_key=groq_api_key)

# Model names
CHAT_MODEL_NAME = "llama-3.1-70b-versatile"
VISION_MODEL_NAME = "llama-3.2-11b-vision-preview"

history = []  # Shared conversation history
MAX_MESSAGE_LENGTH = 1600  # WhatsApp limit

def send_chunked_response(response, twilio_response):
    """Send long responses in chunks."""
    chunks = [response[i:i + MAX_MESSAGE_LENGTH] for i in range(0, len(response), MAX_MESSAGE_LENGTH)]
    for chunk in chunks:
        msg = twilio_response.message()
        msg.body(chunk)

def encode_image(image):
    """Encode image to base64."""
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

def analyze_image(image, prompt):
    """Analyze the uploaded image using the Groq vision model."""
    try:
        base64_image = encode_image(image)
        image_content = {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}

        chat_completion = client_groq.chat.completions.create(
            messages=[
                {"role": "user", "content": [{"type": "text", "text": prompt}, image_content]},
            ],
            model=VISION_MODEL_NAME,
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        return f"Error analyzing image: {str(e)}"

def download_image_with_auth(media_url):
    """Download image from Twilio media URL with authentication."""
    try:
        response = requests.get(media_url, auth=(twilio_account_sid, twilio_auth_token))
        if response.status_code == 200:
            return Image.open(io.BytesIO(response.content))
        else:
            return f"Failed to download image. Status code: {response.status_code}"
    except UnidentifiedImageError:
        return "Unable to identify the uploaded image. Please try again with a valid image."
    except Exception as e:
        return f"Error downloading image: {str(e)}"

def update_history(user_input, assistant_response):
    """Add user input and assistant response to the history."""
    history.append(f"User: {user_input}")
    history.append(f"Assistant: {assistant_response}")
    if len(history) > 10:  # Limit history to last 10 exchanges
        history.pop(0)

@app.route('/sms', methods=['POST'])
def handle_incoming_message():
    try:
        # Retrieve incoming message and media URL
        incoming_message = request.form.get('Body', '').strip()  # Default to empty string if no caption
        media_url = request.form.get('MediaUrl0')

        print(f"Incoming message: {incoming_message}")

        if media_url:
            print(f"Image URL: {media_url}")
            image = download_image_with_auth(media_url)

            if isinstance(image, str):  # Error message returned
                response = image
            else:
                # Use default prompt if no caption provided
                # prompt = incoming_message if incoming_message else "explain the image"
                prompt = f"Explain Simply: {incoming_message}" if incoming_message else "Explain Simply: explain the image"
                response = analyze_image(image, prompt)

                # Update history with the image interaction
                update_history(prompt, response)
        else:
            # Handle text messages normally (without an image)
            if incoming_message.lower() == 'restart':
                print('Restarting app...')
                os.execv(sys.executable, ['python'] + sys.argv)

            # Create conversation prompt from history
            history.append(f"User: {incoming_message}")
            prompt = "\n".join(history[-10:])

            chat_completion = client_groq.chat.completions.create(
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt},
                ],
                model=CHAT_MODEL_NAME,
                temperature=0.5,
                max_tokens=1024,
                top_p=1,
            )
            response = chat_completion.choices[0].message.content

            # Update history with the text interaction
            update_history(incoming_message, response)

        # Create Twilio response
        twilio_response = MessagingResponse()
        send_chunked_response(response, twilio_response)

        return str(twilio_response)

    except Exception as e:
        print(f"Error: {e}")
        return "Error", 500

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)
