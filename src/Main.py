import os
from flask import Flask, request, render_template

from RobotController import RobotController


controller = RobotController("/dev/ttyACM0")


def get_file_path(file_name):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(script_dir, file_name)


def initDXF(filename):
    '''
    Return the DXF text file represented by the file name. The file must be
    in the local folder.

    Arguments:
        filename is of type string. Contains name of image file.
    '''

    file = open(filename)

    # Since dxf is a fancy extension for a text file, it can be read as a string
    DXFtxt = file.readlines()

    file.close()

    return DXFtxt


def sendToSerial(shapes, originX=0, originY=0, originZ=0, writingZ=-26, fastFeed=100, slowFeed=10):

    # G21: Units in millimetres
    # G90: Absolute distances
    controller.send_gcode("G21")
    controller.send_gcode("G90")

    controller.send_gcode(f"G00 X{originX} Y{originY} Z{originZ} F{fastFeed}")

    up = True

    # Assume Z0 is down and cutting and Z1 is retracted up
    for shape in shapes:
        for i in range(len(shape)):
            xstr = "{:.3f}".format(round(originX + shape[i][0], 3))
            ystr = "{:.3f}".format(round(originY + shape[i][1], 3))

            # Write coordinate to file
            controller.send_gcode(f"G01 X{xstr} Y{ystr} F{slowFeed}")

            # When arrived at point of new shape, start cutting
            if up:
                controller.send_gcode(f"G01 Z{writingZ} F{slowFeed}")
                up = False
        # When finished shape, retract cutter
        controller.send_gcode(f"G00 Z{originZ} F{fastFeed}")
        up = True
    # Return to origin (0, 0) when done, then end program with M2
    controller.send_gcode(f"G00 Z{originZ} F{fastFeed}")
    controller.send_gcode(f"G00 X{originX} Y{originY} F{fastFeed}")


def readFromDXF(DXFtxt):
    # Create Image object from file in local folder

    segment = -1

    path = []
    xold = []
    yold = []

    line = 0
    polyline = 0
    is_line = 0
    vertex = 0

    lineOldX = None
    lineOldY = None

    # While there is still more to read
    while line < len(DXFtxt):
        # These are just conditions how to interpret the DXF into coordinates
        if DXFtxt[line] == "POLYLINE\n":
            segment += 1
            polyline = 1
            path.append([])
        elif DXFtxt[line] == "LINE\n":
            is_line = 1

        elif DXFtxt[line] == "VERTEX\n":
            vertex = 1

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

        elif (DXFtxt[line].strip() == "20") & ((vertex == 1) & (polyline == 1)):
            line += 1
            y = float(DXFtxt[line])

            if (x != xold) | (y != yold):
                path[segment].append([float(x), float(y)])
                xold = x
                yold = y

        elif DXFtxt[line] == "SEQEND\n":
            polyline = 0
            vertex = 0

        line += 1

    # Rescale the coordinates to imdim x imdim
    scale(path)

    return path


def scale(path):
    '''
    DXF files have the coordinates prewritten into it, which means they may
    be the wrong dimension. Scale the coordinates read from the DXF to IMDIM.

    Arguments:
        path is of type list. Contains sublists of tuples, where each tuple is
                              an (x, y) coordinate.
    '''

    IMDIM = 50

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
    scale = IMDIM / size  # original

    # Once the old size is known, scale the coordinates
    for i in range(len(path)):
        for j in range(len(path[i])):
            path[i][j][0] *= scale
            path[i][j][1] *= scale

app = Flask(__name__)


# Allowed extensions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() == 'dxf'


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return "No file part", 400

    file = request.files['file']
    if file.filename == '':
        return "No selected file", 400

    if file and allowed_file(file.filename):
        # process the file
        lines = file.stream.readlines()
        if len(lines) <= 0:
            return "lines < 1"
        paths = readFromDXF(lines)
        sendToSerial(paths, originX=150, originY=50, originZ=3, writingZ=1, fastFeed=500, slowFeed=100)
        return f"File printed"
    else:
        return "Invalid file type. Only DXF files are allowed.", 400


if __name__ == '__main__':
    lines = initDXF(get_file_path("./peveko.dxf"))
    paths = readFromDXF(lines)
    sendToSerial(paths, originX=150, originY=50, originZ=3, writingZ=1, fastFeed=500, slowFeed=100)
    # app.run(debug=True, host="0.0.0.0")
    controller.home()