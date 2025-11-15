from flask import Flask, request, jsonify,render_template,session,redirect,url_for
from google import genai
from dotenv import load_dotenv
import serial
import os
import base64
import json
from google.genai import types
from datetime import datetime, timedelta
load_dotenv()
os.makedirs("static", exist_ok=True)
app = Flask(__name__,template_folder='templates')
client = genai.Client(api_key=os.getenv("GENAI_API_KEY"))
#serial =  serial.Serial('/dev/tty.usbmodem1101', 9600, timeout=1)
@app.route("/", methods=["GET", "POST"])     
def home():
    gemini_output = "Upload an image to get a real-time emotion and people count analysis."

    if request.method == "POST":
        image_data = request.form.get("image_data")

        if not image_data:
            gemini_output = "No image received."
            return render_template("index.html", gemini_output=gemini_output)

        header, encoded = image_data.split(",", 1)
        image_bytes = base64.b64decode(encoded)

        filename = f"static/screenshot_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.jpg"
        with open(filename, "wb") as f:
            f.write(image_bytes)

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                "How many people are there and what emotions are displayed in the image?",
                types.Part.from_bytes(
                    data=image_bytes,
                    mime_type="image/jpeg"
                )
            ]
        )

        gemini_output = response.text

    
        
        
    return render_template("index.html", gemini_output = gemini_output)



if __name__ == "__main__":
    app.run(debug=True, port=5000)

