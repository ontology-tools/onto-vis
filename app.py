from flask import Flask, request, url_for, render_template

app = Flask(__name__)

@app.route('/')
@app.route('/home')
def home():
    ontologies = ["BCIO", "AddictO"]
    return render_template("index.html", ontologies=ontologies)