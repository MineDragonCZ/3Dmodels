import serial
import time


class RobotController:
    writing_z = 0.0
    def __init__(self, port, baudrate=115200, timeout=1):
        """
        Initializes the RobotController with a serial connection.

        :param port: The serial port the robot is connected to (e.g., "COM3" or "/dev/ttyUSB0").
        :param baudrate: The baud rate for serial communication (default is 115200).
        :param timeout: Timeout for reading from the serial port (default is 1 second).
        """
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout

        # Initialize the serial connection
        self.serial_connection = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
        time.sleep(2)  # Wait for the connection to establish
        # self.send_gcode("M17")

    def send_gcode(self, gcode):
        """
        Sends a G-code command to the robot.

        :param gcode: The G-code command string (e.g., "G1 X10 Y10 Z10 F100").
        """
        if not self.serial_connection.is_open:
            print("Serial port is not open!")
            return

        # Send G-code to the robot
        self.serial_connection.write((gcode + '\n').encode('utf-8'))
        print(f"Sent: {gcode}")

        # Optionally, read the response (if the robot sends anything back)
        response = ""
        while True:
            response = self.read_response()
            if response and response.startswith("ok"):
                break
            elif response:
                print(f"Received error: {response}")
            time.sleep(0.1)
        print(f"Received: {response}")
        return response

    def read_response(self):
        """
        Reads the response from the robot after sending a G-code command.
        """
        if self.serial_connection.in_waiting > 0:
            response = self.serial_connection.readline().decode('utf-8').strip()
            return response
        return None

    def move_to_position(self, x, y, z, feedrate=100):
        """
        Sends a G-code command to move the robot to a specific position.

        :param x: The X position (in mm).
        :param y: The Y position (in mm).
        :param z: The Z position (in mm).
        :param feedrate: The feedrate (in mm/min) for movement (default is 100).
        """
        gcode = f"G1 X{x} Y{y} Z{z} F{feedrate}"
        self.send_gcode(gcode)

    def home(self):
        """
        Sends a G-code command to home the robot (move to the origin).
        """
        # self.send_gcode("G28")  # G28 is commonly used to home axes
        self.send_gcode("G01 Z0 F10")
        self.send_gcode("G01 X130 Z25 F10")
        # self.send_gcode("M2019")
    def set_speed(self, feedrate):
        """
        Sets the robot's movement speed (feedrate).

        :param feedrate: The speed (in mm/min).
        """
        gcode = f"F{feedrate}"
        self.send_gcode(gcode)

    def close(self):
        """
        Closes the serial connection.
        """
        if self.serial_connection.is_open:
            self.serial_connection.close()
            print("Serial connection closed.")

    def set_writing_z(self):
        response = self.send_gcode("P2220").strip()
        parts = response.split("Z")
        if len(parts) < 2:
            return False
        self.writing_z = float(parts[1]) - 0.1
        return True

    def pen_up(self):
        self.send_gcode(f"G01 Z{self.writing_z + 10}")

    def pen_down(self, z_offset):
        self.send_gcode(f"G01 Z{self.writing_z + z_offset}")

    def calibrate(self):
        self.send_gcode("G01 X180 Y0 Z20 F10")
        self.send_gcode("M2019")
        time.sleep(2)
        self.set_writing_z()
        time.sleep(2)
        self.send_gcode("M17")


