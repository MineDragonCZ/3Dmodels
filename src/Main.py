import os

from im2glib.gInit import initDXF

import RobotController as rc

controller = rc.RobotController("/dev/ttyACM0")


def get_file_path(file_name):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(script_dir, file_name)


def scale(paths, dimension=100):

    for path_index in range(len(paths)):
        path = paths[path_index]
        # Create lists of only x coordinates and only y coordinates
        x = []
        y = []

        for shape in path:
            print(shape)
            x.append(shape[0])
            y.append(shape[1])

        # To scale from the old size to imdim, must know the old size
        maxx = max(x)
        maxy = max(y)

        minx = min(x)
        miny = min(y)

        # The distance between the minimal coordinate and the edge is the margin,
        # assumed size is the maximal coordinate plus the margin
        margin = min(minx, miny)
        size = max(maxx, maxy) + margin
        new_size = dimension / size

        # Once the old size is known, scale the coordinates
        for i in range(len(path)):
            path[i][0] *= new_size
            path[i][1] *= new_size


def sendToSerial(shapes, originX=0, originY=0, originZ=0, writingZ=-26, fastFeed=100, slowFeed=10):

    # Boilerplate text:
    # G17: Select X, Y plane
    # G21: Units in millimetres
    # G90: Absolute distances
    # G54: Coordinate system 1
    # controller.send_gcode("G17")
    controller.send_gcode("G21")
    controller.send_gcode("G90")
    # controller.send_gcode("G54")

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


def readFromDXF(filename):
    # Create Image object from file in local folder
    dxf_txt = initDXF(filename)

    segment = -1

    path = []
    xold = None
    yold = None

    originX = 0;
    originY = 0;

    x = None
    y = None

    line = 0
    polyline = False
    vertex = False

    # While there is still more to read
    while line < len(dxf_txt):
        # These are just conditions how to interpret the DXF into coordinates
        if dxf_txt[line] == "POLYLINE\n":
            segment += 1
            polyline = True
            path.append([])

        elif dxf_txt[line] == "VERTEX\n":
            vertex = True

        elif (dxf_txt[line].strip() == "66") & (x is not None) & (y is not None):
            line += 1
            if dxf_txt[line].strip() == "1":
                originX = x
                originY = y

        elif (dxf_txt[line].strip() == "10") & vertex & polyline:
            line += 1
            x = float(dxf_txt[line])

        elif (dxf_txt[line].strip() == "20") & vertex & polyline:
            line += 1
            y = float(dxf_txt[line])

            if (x != xold) | (y != yold):
                path[segment].append([float(x), float(y)])
                xold = x
                yold = y

        elif dxf_txt[line] == "SEQEND\n":
            polyline = False
            vertex = False

        line += 1
    return path


paths = readFromDXF(get_file_path("dxffile.dxf"))
scale(paths, dimension=50)
controller.send_gcode("M17")
sendToSerial(paths, originX=150, originY=50, originZ=0, writingZ=-15, fastFeed=200, slowFeed=10)
