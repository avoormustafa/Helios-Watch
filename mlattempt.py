import json
import numpy as np

# 1. Define all 19 space weather column headers exactly as requested
HEADERS = [
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

def load_lst_to_numpy(filename="data.txt"):
    all_rows = []

    with open(filename, "r", encoding="utf-8") as f:
        for line in f:
            # Strip out trailing text labels safely if present
            if " . " in line:
                line = line.split(" . ")[0]
                
            columns = line.split()
            if not columns:
                continue
                
            # Convert values to numbers dynamically
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

    # Transpose rows into horizontal columns
    all_columns = list(zip(*all_rows))

    # Construct a dictionary mapping each precise header to a NumPy array
    numpy_data = {}
    for index, col_data in enumerate(all_columns):
        if index < len(HEADERS):
            header_name = HEADERS[index]
        else:
            header_name = f"column_{index + 1}"  # Fallback for extra data columns
            
        numpy_data[header_name] = np.array(col_data)
        
    return numpy_data

# --- Execute Code ---
# Load all data from your .lst file
space_data = load_lst_to_numpy("data.txt")

# --- Access individual variables as distinct NumPy arrays ---
year             = space_data["year"]
day              = space_data["day"]
hour             = space_data["hour"]
scalar           = space_data["scalar"]
bx_gse_gsm       = space_data["BX_nT_GSE_GSM"]
by_gse           = space_data["BY_nT_GSE"]
bz_gse           = space_data["BZ_nT_GSE"]
by_gsm           = space_data["BY_nT_GSM"]
bz_gsm           = space_data["BZ_nT_GSM"]
rms_mag          = space_data["RMS_magnitude"]
rms_vec          = space_data["RMS_field_vector"]
sw_plasma_temp   = space_data["SW_Plasma_temp"]
proton_dens      = space_data["proton_dens"]
plasma_speed     = space_data["plasma_speed"]
flow_pressure    = space_data["flow_pressure"]
electric_field   = space_data["electric_field"]
kp_index         = space_data["Kp_index"]
dst_index        = space_data["Dst_index"]
ae_index         = space_data["AE_index"]

# --- Verification Check ---
print(f"Loaded {len(space_data)} total columns into NumPy.")
print("Example - Scalar Array:", scalar)
print("Example - SW Plasma Temp Array:", sw_plasma_temp)
