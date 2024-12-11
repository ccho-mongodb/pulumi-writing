import os
from flask import Flask
app = Flask(__name__)

@app.route("/")
def hello():
    secret_msg = os.environ.get("MY_MESSAGE") or ""
    return f"Your secret message is {secret_msg}"

if __name__ == '__main__':
    app.run()