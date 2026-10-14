import json

input_filename = "data.txt"
output_filename = "data.json"

# The precise column names you requested mapped in sequential order
headers = [
    "year",
    "day",
    "hour",
    "scalar",
    "BX_nT_GSE_GSM",
    "BY_nT_GSE",
    "BZ_nT_GSE",
    "BY_nT_GSM",
    "BZ_nT_GSM",
    "RMS_magnitude",
    "RMS_field_vector",
    "SW_Plasma_temp",
    "proton_dens",
    "plasma_speed",
    "flow_pressure",
    "electric_field",
    "Kp_index",
    "Dst_index",
    "AE_index"
]

all_rows = []

with open(input_filename, "r", encoding="utf-8") as f:
    for line in f:
        # Strip trailing notes cleanly
        if " . " in line:
            line = line.split(" . ")[0]
            
        columns = line.split()
        if not columns:
            continue
            
        parsed_row = []
        for value in columns:
            try:
                if "." in value:
                    parsed_row.append(float(value))
                else:
                    parsed_row.append(int(value))
            except ValueError:
                parsed_row.append(value)
                
        all_rows.append(parsed_row)

# Transpose rows to columns
all_columns = list(zip(*all_rows))

# Build individual objects for each specific column name
json_output = []
for index, col_data in enumerate(all_columns):
    # Fallback to an index name if the input file has more columns than headers provided
    column_name = headers[index] if index < len(headers) else f"column_{index + 1}"
    
    column_object = {
        "column_name": column_name,
        "values": list(col_data)
    }
    json_output.append(column_object)

# Export the structured output
with open(output_filename, "w", encoding="utf-8") as out_file:
    json.dump(json_output, out_file, indent=4)

print(f"Successfully generated {output_filename} with named column objects!")
