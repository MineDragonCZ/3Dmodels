import ezdxf


def convert_lines_to_polylines(input_file, output_file):
    # Load the DXF file
    try:
        doc = ezdxf.readfile(input_file)
    except ezdxf.DXFError as e:
        print(f"Error reading DXF file: {e}")
        return

    # Create a new DXF document in R2000 format
    new_doc = ezdxf.new(dxfversion="R2000")
    new_msp = new_doc.modelspace()

    # Collect lines and convert to polylines
    lines = []
    for line in doc.modelspace().query("LINE"):
        start = tuple(line.dxf.start)
        end = tuple(line.dxf.end)
        lines.append((start, end))

    # Group lines into polylines
    used_lines = set()
    polylines = []

    while lines:
        polyline_points = []
        for i, (start, end) in enumerate(lines):
            if not polyline_points:
                polyline_points.append(start)
                polyline_points.append(end)
                used_lines.add(i)
            elif start == polyline_points[-1]:
                polyline_points.append(end)
                used_lines.add(i)
            elif end == polyline_points[-1]:
                polyline_points.append(start)
                used_lines.add(i)

        if polyline_points:
            polylines.append(polyline_points)

    # Add polylines to the new DXF document
    for points in polylines:
        new_msp.add_polyline2d(points, close=False)

    # Save the output DXF
    new_doc.saveas(output_file)
    print(f"Converted lines to polylines and saved in {output_file}")


# Input and output files
input_dxf = "peveko.dxf"  # Path to your DXF file with lines
output_dxf = "peveko_new.dxf"  # Path to save the DXF file with polylines

# Convert lines to polylines
convert_lines_to_polylines(input_dxf, output_dxf)
