import glob
import json
import os
import sys
from datetime import datetime, timedelta
from threading import Thread

import serial
from flask import Flask, request, render_template

from RobotController import RobotController

controller: (RobotController | None) = None


def get_file_path(file_name):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(script_dir, file_name)


def initDXF(filename):
    file = open(filename)

    # Since dxf is a fancy extension for a text file, it can be read as a string
    DXFtxt = file.readlines()

    file.close()

    return DXFtxt


stop_drawing: bool = False
is_drawing: bool = False
drawing_status: float = 0
drawing_status_time_left: str = ""
drawing_start: datetime | None = None

drawing_speed: int = 0
drawing_points_total: int = 0
drawing_points_done: int = 0
drawing_points_lost: int = 0
drawing_size: str = "File not uploaded!"
writing_origin = []


def estimate_time_to_finish():
    global drawing_start
    global drawing_status
    if drawing_start is None:
        return timedelta()

    if drawing_status <= 0:
        return timedelta()

    # Calculate elapsed time
    current_time = datetime.now()
    elapsed_time = current_time - drawing_start

    # Calculate remaining time
    remaining_ratio = (100 - (drawing_status * 100)) / (drawing_status * 100)
    estimated_remaining_time = elapsed_time * remaining_ratio

    return estimated_remaining_time


def calculate_arm_speed():
    global drawing_start
    global drawing_points_done
    if drawing_start is None:
        return 0

    # Calculate elapsed time
    current_time = datetime.now()
    elapsed_time = current_time - drawing_start

    if elapsed_time.total_seconds() <= 0:
        return 0

    pps = drawing_points_done / elapsed_time.total_seconds()

    return int(pps)


def sendToSerial(outline, shapes, fastFeed=100, slowFeed=10):
    if controller is None:
        return
    global stop_drawing
    global is_drawing
    global drawing_status
    global drawing_status_time_left
    global drawing_start
    global writing_origin
    global drawing_speed, drawing_points_total, drawing_points_done, drawing_points_lost
    if is_drawing:
        return
    is_drawing = True
    # G21: Units in millimetres
    # G90: Absolute distances
    controller.send_gcode("G21")
    controller.send_gcode("G90")

    # controller.calibrate()
    originX = writing_origin[0]
    originY = writing_origin[1]
    writingZ = writing_origin[2]
    controller.writing_z = writingZ

    controller.send_gcode(f"M17")
    controller.send_gcode(f"G01 X{originX} Y{originY} Z{writingZ + 30} F{slowFeed}")
    if stop_drawing:
        stop_drawing = False
        return

    if outline:
        if len(shapes) < 4:
            stop_drawing = False
            is_drawing = False
            return
        minX = shapes[0]
        minY = shapes[1]
        maxX = shapes[2]
        maxY = shapes[3]
        controller.pen_up()
        if stop_drawing:
            stop_drawing = False
            return
        controller.send_gcode(f"G01 X{originX + minX + maxX} Y{originY + minY} F{slowFeed}")
        if stop_drawing:
            stop_drawing = False
            return
        controller.send_gcode(f"G01 X{originX + minX + maxX} Y{originY + minY + maxY} F{slowFeed}")
        if stop_drawing:
            stop_drawing = False
            return
        controller.send_gcode(f"G01 X{originX + minX} Y{originY + minY + maxY} F{slowFeed}")
        if stop_drawing:
            stop_drawing = False
            return
        controller.send_gcode(f"G01 X{originX + minX} Y{originY + minY} F{slowFeed}")

        # controller.send_gcode(f"G00 Z{writingZ + 30} F{fastFeed}")
        stop_drawing = False
        is_drawing = False
        return

    up = True
    drawing_start = datetime.now()

    drawing_points_done = 0
    for shape in shapes:
        if stop_drawing:
            controller.pen_up()
            break
        for i in range(len(shape)):
            drawing_points_done += 1
            if stop_drawing:
                controller.pen_up()
                break
            x = originX + shape[i][0]
            y = originY + shape[i][1]
            z_offset = -0.1  # math.sqrt(math.pow(x - originX, 2) + math.pow(y - originY, 2)) / 500.0 - 0.1
            xstr = "{:.3f}".format(round(x, 3))
            ystr = "{:.3f}".format(round(y, 3))

            # Write coordinate to file
            controller.send_gcode(f"G01 X{xstr} Y{ystr} F{slowFeed}")
            drawing_status = drawing_points_done / drawing_points_total
            drawing_status_time_left = estimate_time_to_finish()
            drawing_speed = calculate_arm_speed()

            # When arrived at point of new shape, start cutting
            if up:
                controller.pen_down(z_offset)
                # controller.send_gcode(f"G01 Z{writingZ} F{slowFeed}")
                up = False
        # When finished shape, retract cutter
        controller.pen_up()
        # controller.send_gcode(f"G00 Z{originZ} F{fastFeed}")
        up = True
    # Return to origin (0, 0) when done, then end program with M2
    controller.pen_up()
    # controller.send_gcode(f"G00 Z{originZ} F{fastFeed}")
    controller.send_gcode(f"G00 X{originX} Y{originY} F{fastFeed}")
    # controller.send_gcode("M2019") # release
    frequency = 800
    if stop_drawing:
        frequency = 1000
    controller.send_gcode(f"M2210 F{frequency} T500")
    stop_drawing = False
    is_drawing = False


def readFromDXF(DXFtxt, size=50.0):
    # Create Image object from file in local folder

    segment = -1

    path = []
    xold = []
    yold = []

    xFirst: float = None
    yFirst: float = None
    isFirstVertex = False
    loopPolyline = False

    line = 0
    polyline = 0
    is_line = 0
    vertex = 0

    lineOldX = None
    lineOldY = None
    x = None

    # While there is still more to read
    while line < len(DXFtxt):
        # These are just conditions how to interpret the DXF into coordinates
        if DXFtxt[line] == "POLYLINE\n":
            segment += 1
            polyline = 1
            isFirstVertex = True
            path.append([])
        elif DXFtxt[line] == "LINE\n":
            is_line = 1

        elif DXFtxt[line] == "VERTEX\n":
            vertex = 1

        elif polyline == 1 and vertex != 1 and isFirstVertex and DXFtxt[line].strip() == "70":
            loopPolyline = True

        elif loopPolyline and polyline == 1 and DXFtxt[line] == "SEQEND\n" and yFirst is not None and xFirst is not None:
            path[segment].append([float(xFirst), float(yFirst)])
            loopPolyline = False

        elif is_line == 1:
            if DXFtxt[line].strip() == "10":
                line += 1
                x = float(DXFtxt[line])
            elif DXFtxt[line].strip() == "20":
                line += 1
                y = float(DXFtxt[line])
                if (lineOldX is None) | (lineOldY is None):
                    segment += 1
                    path.append([])
                elif (abs(lineOldX - x) > 0.5) | (abs(lineOldY - y) > 0.5):
                    segment += 1
                    path.append([])
                path[segment].append([float(x), float(y)])
            elif DXFtxt[line].strip() == "11":
                line += 1
                x = float(DXFtxt[line])
                lineOldX = x
            elif DXFtxt[line].strip() == "21":
                line += 1
                y = float(DXFtxt[line])
                lineOldY = y
                path[segment].append([float(x), float(y)])
                is_line = 0

        elif (DXFtxt[line].strip() == "10") & ((vertex == 1) & (polyline == 1)):
            line += 1
            x = float(DXFtxt[line])
            if isFirstVertex:
                xFirst = x

        elif (DXFtxt[line].strip() == "20") & ((vertex == 1) & (polyline == 1)):
            line += 1
            y = float(DXFtxt[line])
            if isFirstVertex:
                isFirstVertex = False
                yFirst = y

            if (x != xold) | (y != yold):
                path[segment].append([float(x), float(y)])
                xold = x
                yold = y

        elif DXFtxt[line] == "SEQEND\n":
            polyline = 0
            vertex = 0

        line += 1

    # Rescale the coordinates to imdim x imdim
    maxPos = scale(path, size)

    return [maxPos, path]


def scale(path, custom_size):
    global drawing_size
    # Create lists of only x coordinates and only y coordinates
    x = []
    y = []

    for shape in path:
        for coord in shape:
            x.append(coord[0])
            y.append(coord[1])

    # To scale from the old size to imdim, must know the old size
    maxx = max(x)
    maxy = max(y)

    minx = min(x)
    miny = min(y)

    # The distance between the minimal coordinate and the edge is the margin,
    # assumed size is the maximal coordinate plus the margin
    margin = min(minx, miny)
    size = max(maxx, maxy) + margin
    scale = custom_size / size  # original

    # Once the old size is known, scale the coordinates
    for i in range(len(path)):
        for j in range(len(path[i])):
            path[i][j][0] *= scale
            path[i][j][1] *= scale
    drawing_size = f"{maxx * scale}x{maxy * scale} mm"
    return [minx * scale, miny * scale, maxx * scale, maxy * scale]


def serial_ports():
    if sys.platform.startswith('win'):
        ports = ['COM%s' % (i + 1) for i in range(256)]
    elif sys.platform.startswith('linux') or sys.platform.startswith('cygwin'):
        # this excludes your current terminal "/dev/tty"
        ports = glob.glob('/dev/tty[A-Za-z]*')
    elif sys.platform.startswith('darwin'):
        ports = glob.glob('/dev/tty.*')
    else:
        raise EnvironmentError('Unsupported platform')

    result = []
    for port in ports:
        try:
            # s = serial.Serial(port)
            # s.close()
            result.append(port)
        except (OSError, serial.SerialException):
            pass
    return result


app = Flask(__name__)


# Allowed extensions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() == 'dxf'


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/upload', methods=['POST'])
def upload_file():
    outline = False
    if controller is None:
        return "Please select proper Serial Port", 400
    if is_drawing:
        return "Arm is already drawing", 400
    if len(writing_origin) < 3:
        return "Origin is not set", 400
    if 'file' not in request.files:
        return "No file part", 400

    if request.form.get('outline'):
        outline = True

    file = request.files['file']
    size = float(request.form.get("size"))
    if file.filename == '':
        return "No selected file", 400

    global drawing_points_total

    if file and allowed_file(file.filename):
        # process the file
        lines = file.stream.readlines()
        if len(lines) <= 0:
            return "lines < 1", 400
        lines = [line.decode('utf-8').strip() + "\n" for line in lines]
        paths = readFromDXF(lines, size)

        drawing_points_total = 0
        for shape in paths[1]:
            for i in range(len(shape)):
                drawing_points_total += 1
        if drawing_points_total == 0:
            drawing_points_total = 1

        if outline:
            thread = Thread(target=sendToSerial, args=(True, paths[0], 100, 10))
            thread.start()
            return "Doing outline...", 200
        thread = Thread(target=sendToSerial, args=(False, paths[1], 500, 20))
        thread.start()
        return "Print started", 200
    else:
        return "Invalid file type. Only DXF files are allowed.", 400


@app.route("/api/getstatus")
def get_status():
    obj = {
        "percentage": str(round(drawing_status * 100, 2)),
        "time": str(drawing_status_time_left),
        "speed": str(drawing_speed),
        "points_lost": str(drawing_points_lost),
        "points_total": str(drawing_points_total),
        "points_done": str(drawing_points_done),
        "size": str(drawing_size),
        "origin": ("Not set!" if len(
            writing_origin) < 3 else f"X{writing_origin[0]} Y{writing_origin[1]} Z{writing_origin[2]}"),
    }
    return json.dumps(obj)


@app.route("/api/setorigin")
def set_writing_origin():
    global controller
    if controller is None:
        return "Controller is not connected", 400
    if is_drawing:
        return "Arm is drawing", 400
    global writing_origin
    writing_origin = controller.get_current_pos()
    return "Origin set successfully", 200


@app.route("/api/servos/lock")
def servos_lock():
    global controller
    if controller is None:
        return "Controller is not connected", 400
    controller.send_gcode("M17")
    return "Servos are locked now", 200


@app.route("/api/servos/unlock")
def servos_unlock():
    global controller
    if controller is None:
        return "Controller is not connected", 400
    controller.send_gcode("M2019")
    return "Servos are unlocked now", 200


@app.route("/api/setport", methods=['POST'])
def set_com():
    global controller
    if controller is not None:
        controller.close()
    p = request.json["port"]
    if p == "" or p is None:
        return "Disconnected!", 200
    try:
        controller = RobotController(port=p)
        return "Connected!", 200
    except Exception:
        return "Connection error", 400


@app.route("/api/getports")
def get_coms():
    return json.dumps(serial_ports()), 200


@app.route('/api/stopdrawing')
def stop_drawing_file():
    global is_drawing
    global stop_drawing
    if (not is_drawing) or stop_drawing:
        return "Not drawing", 400
    if controller is not None:
        controller.halt = True
    stop_drawing = True
    is_drawing = False
    return "Stopped drawing", 200


if __name__ == '__main__':
    app.run(debug=False, host="0.0.0.0")
