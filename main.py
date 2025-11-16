from flask import Flask, request, jsonify,render_template,session,redirect,url_for,Response
from google import genai
from dotenv import load_dotenv
import serial
import os
import base64
import json
from google.genai import types
from datetime import datetime
import threading
from flask_sqlalchemy import SQLAlchemy
load_dotenv()
os.makedirs("static", exist_ok=True)
app = Flask(__name__,template_folder='templates')
client = genai.Client(api_key=os.getenv("GENAI_API_KEY"))
ser =  serial.Serial('/dev/cu.usbmodem145201', 9600, timeout=1)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = os.urandom(24)
db = SQLAlchemy(app)
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    vibe= db.Column(db.String, default="0")
def read_arduino():
    """Returns one full line from Arduino if available."""
    if ser.in_waiting > 0:
        try:
            line = ser.readline().decode("utf-8", errors="ignore").strip()
            return line
        except:
            return None
    return None

def arduino_listener():
    while True:
        line = read_arduino()
        if line:
            print("[Arduino → Python]", line)

arduino_thread = threading.Thread(target=arduino_listener, daemon=True)
arduino_thread.start()

@app.route('/poopdoop')
def export_users():
    users = User.query.all()
    def generate():
        data = [['id', 'username', 'password', 'vibe']]
        for user in users:
            data.append([user.id, user.username, user.password, user.vibe])
        for row in data:
            yield ','.join(map(str, row)) + '\n'
    return Response(generate(), mimetype='text/csv',
                    headers={"Content-Disposition": "attachment;filename=users.csv"})
@app.route('/', methods = ['GET','POST'])
def signin():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if not username or not password:  # Added validation
            return render_template('signin.html', error="Please enter both username and password.")
        existing_user = User.query.filter_by(username=username, password = password).first()
        if existing_user:
            session['username'] = username
            db.session.commit()
            print("The session user is:" , session.get('username'))
            return redirect(url_for('profile'))
        
        new_user = User(username=username, password=password)
        db.session.add(new_user)
        db.session.commit()
        session['username'] = username
        print("The session user is:" , session.get('username'))
        
        return redirect(url_for('profile'))
    return render_template('signin.html')

@app.route('/profile', methods = ['GET','POST'])
def profile():
    if 'username' not in session:
        return redirect(url_for('signin'))
    username = session['username']
    user = User.query.filter_by(username=username).first()
    if user is None:
        return redirect(url_for('signin'))
    if user.vibe is None or user.vibe == '0':
        if request.method == 'POST':
            vibe = request.form.get('vibe')
            user.vibe = vibe
            db.session.commit()
            session['vibe'] =user.vibe
            return render_template('index.html', username = username, vibe=user.vibe)
           
    else:
        return render_template('index.html', username=username, vibe=user.vibe)
    return render_template('profile.html', username=username)
@app.route("/analyze", methods=["GET", "POST"])     
def analyze():
    print("The session user is:" , session.get('username'))

    if 'username' not in session:
        return redirect(url_for('signin'))
    
    username = session['username']
    user = User.query.filter_by(username=username).first()
    if user is None:
        return redirect(url_for('signin'))
    if not user.vibe or user.vibe == '0':
        return redirect(url_for('profile'))
    gemini_output = "Upload an image to get a real-time emotion and people count analysis."
    if request.method == "POST":
        image_data = request.form.get("image_data")
        
        if not image_data:
            gemini_output = "No image received."
            return render_template("index.html", gemini_output=gemini_output)

        header, encoded = image_data.split(",", 1)
        image_bytes = base64.b64decode(encoded)
        arduino_data = read_arduino() if ser.in_waiting > 0 else "No sensor data available"

        filename = f"static/screenshot_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.jpg"
        with open(filename, "wb") as f:
            f.write(image_bytes)

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                """Given the following picture analyze the amount of people and the emotions(are they chill or aggressive) of each person.
                Rank the overall vibe of the room on a scale of 1-10 (1 being very chill, and 10 is very aggressive)
                given the following data {arduino_data}, from an ultrasonic to detect distance between people, a sound sensor, and a motion sensor. Create a consise 
                response about what a nuerodivergent person with this vibe should say {user.vibe} 
                Return in this format: {"vibe_score":x, "text":"advice"} Make sure tyhat the response is in valid json.
                  """,
                types.Part.from_bytes(
                    data=image_bytes,
                    mime_type="image/jpeg"
                )
            ]
        )


        
        gemini_output = response.text.strip()
        start_idx = gemini_output.find('{')
        end_idx = gemini_output.rfind('}')
        
        clean_json_string = ""
        if start_idx != -1 and end_idx != -1:
            clean_json_string = gemini_output[start_idx:end_idx+1].strip()
        else:
            # If we can't find the JSON delimiters, use the whole text
            clean_json_string = gemini_output
        my_dict = json.loads(clean_json_string)

        oop = my_dict['vibe_score']
        message = f"SCORE:{oop}\n"
        ser.write(message.encode("utf-8"))
        print("[Python → Arduino]", message)
    return render_template("index.html",gemini_output=my_dict.get("text", "No output"),
                       vibe=user.vibe)


if __name__ == "__main__":
    app.run(debug=True, port=5000)

