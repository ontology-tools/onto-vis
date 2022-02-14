from flask import Flask, request, url_for, render_template

app = Flask(__name__)

@app.route('/')
@app.route('/home')
def home():
    return render_template("index.html")