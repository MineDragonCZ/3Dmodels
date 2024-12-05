import ezdxf
import os

def dxf_to_coords(file_path):
    try:
        doc = ezdxf.readfile(file_path)
        msp = doc.modelspace()

        all_coords = []

        for entity in msp:
            if entity.dxftype() == "LINE":
                start = entity.dxf.start
                end = entity.dxf.end
                all_coords.append([[start.x, start.y], [end.x, end.y]])

            elif entity.dxftype() == "LWPOLYLINE":
                point = []
                point[0] = entity.ocs().to_wcs(entity.dxf.center).x
                point[1] = entity.ocs().to_wcs(entity.dxf.center).y
                points = [point[0], point[1]]
                all_coords.append(points)

            elif entity.dxftype() == "POLYLINE":
                point = []
                point[0] = entity.ocs().to_wcs(entity.ocs().uz).x
                point[1] = entity.ocs().to_wcs(entity.dxf).y
                points = [point[0], point[1]]
                all_coords.append(points)

            # Add other entity types as needed, e.g., ARC, SPLINE, etc.

        return all_coords

    except Exception as e:
        print(f"Error: {e}")
        return []

def get_file_path(file_name):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(script_dir, file_name)

# Example usage:
coordinates = dxf_to_coords(get_file_path("./dxffile.dxf"))
print(coordinates)
