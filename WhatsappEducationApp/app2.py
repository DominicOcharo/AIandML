import os
import sys
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
from dotenv import load_dotenv
from groq import Groq  # Import Groq client

# Load environment variables from .env
load_dotenv()

app = Flask(__name__)

# Retrieve API keys and credentials from .env
twilio_account_sid = os.getenv("TWILIO_ACCOUNT_SID")
twilio_auth_token = os.getenv("TWILIO_AUTH_TOKEN")
groq_api_key = os.getenv("GROQ_API_KEY")

# Initialize Twilio and Groq clients
twilio_client = Client(twilio_account_sid, twilio_auth_token)
client_groq = Groq(api_key=groq_api_key)

# Chat model to use
MODEL_NAME = "llama-3.1-70b-versatile"

# Store chat history
history = []

# Max message length for WhatsApp
MAX_MESSAGE_LENGTH = 1600  # WhatsApp's character limit

def send_chunked_response(response, twilio_response):
    """Split and send long responses as multiple WhatsApp messages."""
    chunks = [response[i:i + MAX_MESSAGE_LENGTH] for i in range(0, len(response), MAX_MESSAGE_LENGTH)]
    for chunk in chunks:
        msg = twilio_response.message()
        msg.body(chunk)

def format_prompt(incoming_message, history):
    """Format the chat history to ensure smooth conversations."""
    # Only keep the relevant part of the conversation for context.
    formatted_history = "\n".join(history[-10:])  # Limit to last 10 interactions
    prompt = (
        f"User: {incoming_message}\n"
        f"Previous context:\n{formatted_history}\n"
        "Please respond based on the context and this latest query."
    )
    return prompt

@app.route('/sms', methods=['POST'])
def handle_incoming_message():
    try:
        # Get the message body from the incoming request
        incoming_message = request.form['Body'].strip()
        print(f"Incoming message: {incoming_message}")

        # Handle 'restart' command
        if incoming_message.lower() == 'restart':
            print('Restarting app...')
            os.execv(sys.executable, ['python'] + sys.argv)

        # Add the user's message to the chat history
        history.append(f"User: {incoming_message}")
        if len(history) > 10:
            history.pop(0)  # Keep history limited to the latest 10 messages

        # Generate the prompt with formatted history
        prompt = format_prompt(incoming_message, history)
        print(f"Generated prompt:\n{prompt}")

        # Send the prompt to the Groq-powered Llama model
        chat_completion = client_groq.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ],
            model=MODEL_NAME,
            temperature=0.5,
            max_tokens=1024,
            top_p=1,
        )

        # Extract the model's response
        response = chat_completion.choices[0].message.content
        print(f"Model response: {response}")

        # Add the response to the history
        history.append(f"Assistant: {response}")
        if len(history) > 10:
            history.pop(0)

        print(f"Updated history: {history}")

        # Create a Twilio MessagingResponse to send the reply
        twilio_response = MessagingResponse()

        # Send the response in chunks if it's too long
        send_chunked_response(response, twilio_response)

        print(f"Twilio response: {twilio_response}")

        # Return the Twilio MessagingResponse
        return str(twilio_response)

    except Exception as e:
        print(f"Error: {e}")
        return "Error", 500

if __name__ == '__main__':
    # Run the app on port 5000
    app.run(debug=True, host='127.0.0.1', port=5000)
