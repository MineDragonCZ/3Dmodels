from flask import Flask
import RobotController as rc

#robot = rc.RobotController(port="/dev/ttyACM0")

app = Flask(__name__)

@app.route("/")
def index_route():
    return "<h2>Hello world</h2>"
