# -*- coding: utf-8 -*-
"""
BIM-Sensor Fusion Data Generator

This script extracts data using the Autodesk.Revit.DB.Analysis namespace to
calculate room volumes and thermal transmittances. It simulates a first-order
heat balance equation to generate a ground-truth temperature profile and
synthesizes sensor drift and anomalies for Kalman Filter evaluation.
"""
import clr
import math
import random
import csv
import os
clr.AddReference('RevitAPI')
from Autodesk.Revit.DB import FilteredElementCollector, Transaction, XYZ
from Autodesk.Revit.DB.Analysis import (
    EnergyAnalysisDetailModel,
    EnergyAnalysisDetailModelOptions,
    EnergyModelType
)

# Constants
SQ_FT_TO_SQ_M = 0.092903
CU_FT_TO_CU_M = 0.0283168
RHO = 1.225         # Air density (kg/m3)
CP = 1006           # Specific heat of air (J/kgK)
DELTA_T = 60        # Time step in seconds (1 minute)
Q_HEATER_MAX = 7000 # 7kW

# Set random seed for documented reproducibility / deterministic synthetic noise
random.seed(42)

def get_analytical_area(surface):
    """Calculates the area of an analytical surface using its 3D polygon points"""
    total_area = 0.0
    for poly in surface.GetPolyloops():
        pts = poly.GetPoints()
        n = pts.Count
        if n >= 3:
            area_vector = XYZ.Zero
            for i in range(n):
                area_vector += pts[i].CrossProduct(pts[(i + 1) % n])
            total_area += area_vector.GetLength() / 2.0
    return total_area

def extract_room_data(doc, spaces):
    """Extracts thermal properties from analytical spaces"""
    results = []
    
    for space in spaces:
        print("\nExtracting Room: {}".format(space.SpaceName))
        room_data = {
            "Name": space.SpaceName,
            "Volume": space.Volume * CU_FT_TO_CU_M,
            "Sum_UA": 0.0,
            "Total_L": 0.0,      
            "Surface_Count": 0   
        }
        
        for surf in space.GetAnalyticalSurfaces():
            if "Exterior" in surf.SurfaceType.ToString() or "Window" in surf.SurfaceType.ToString():
                area = get_analytical_area(surf) * SQ_FT_TO_SQ_M
                
                link_id = surf.OriginatingElementId
                actual_id = link_id.HostElementId if hasattr(link_id, "HostElementId") else link_id 
                element = doc.GetElement(actual_id)
                
                if not element:
                    continue
                
                u_value, thickness = 0.0, 0.0
                el_type = doc.GetElement(element.GetTypeId())
                
                # Extract from Walls
                if hasattr(element, "WallType"):
                    if element.WallType.ThermalProperties:
                        u_value = element.WallType.ThermalProperties.HeatTransferCoefficient
                    thickness = element.WallType.Width * 0.3048
                
                # Extract from Floors/Slabs safely
                elif hasattr(element, "FloorType"):
                    if element.FloorType.ThermalProperties:
                        u_value = element.FloorType.ThermalProperties.HeatTransferCoefficient
                    
                    compound_structure = element.FloorType.GetCompoundStructure()
                    if compound_structure:
                        thickness = compound_structure.GetTotalThickness() * 0.3048
                    
                # Extract from Windows/Doors/Roofs
                elif el_type:
                    for name in ["U-Value", "U-Factor", "Thermal Transmittance", "Heat Transfer Coefficient"]:
                        p = el_type.LookupParameter(name)
                        if p and p.HasValue:
                            u_value = p.AsDouble()
                            break
                    
                    for name in ["Thickness", "Width", "Frame Width"]:
                        p = el_type.LookupParameter(name)
                        if p and p.HasValue:
                            thickness = p.AsDouble() * 0.3048
                            break

                # Save and Print Data
                print("  Surface ID: {:<10} | Type: {:<15} | Area: {:>6.2f} m2 | U-Value: {:>6.4f} W/m2K | U*A: {:>6.2f} W/K".format(
                    actual_id.ToString(), surf.SurfaceType.ToString(), area, u_value, u_value * area))
                    
                room_data["Sum_UA"] += (u_value * area)
                if thickness > 0:
                    room_data["Total_L"] += thickness
                    room_data["Surface_Count"] += 1
                
                if u_value == 0.0:
                    print("WARNING: No U-Value for element ID: {}".format(actual_id.ToString()))
                            
        room_data["Avg_L"] = room_data["Total_L"] / room_data["Surface_Count"] if room_data["Surface_Count"] > 0 else 0.1
        results.append(room_data)
        
    return results

def run_simulation(results):
    """
    Runs a 24-hour thermal prediction based on room data with synthetic weather
    and generates a dataset.

    Mathematical Derivation (First-Order Heat Balance):
    dT = (Q_gain - Q_loss) / (rho * V * Cp * C_multiplier) * dt
    Where:
        Q_gain = Heater output (W)
        Q_loss = Sum(U * A) * (T_indoor - T_outdoor)
        rho = Air density
        V = Volume
        Cp = Specific heat capacity
    """
    print("\n--- 24-HOUR TEMPERATURE PREDICTION & SENSOR GENERATION ---")

    TOTAL_MINUTES = 1440

    t_out_profile = []
    base_temp = -2.0     
    amplitude = 4.0      
    out_noise = 0.0

    for m in range(TOTAL_MINUTES):
        time_factor = math.sin((m - 600) * (2 * math.pi / TOTAL_MINUTES))
        diurnal_temp = base_temp + (amplitude * time_factor)
        out_noise = 0.9 * out_noise + random.gauss(0, 0.2)
        noisy_temp = diurnal_temp + out_noise
        t_out_profile.append(noisy_temp)

    desktop_path = os.path.join(os.path.expanduser("~"), "Desktop", "Kalman_Dataset.csv")

    with open(desktop_path, mode='w') as csv_file:
        fieldnames =['Minute', 'T_Out', 'Heater_Status', 'T_Indoor_True', 'T_Sensor_Noisy']
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames, lineterminator='\n')
        writer.writeheader()

        for r in results:
            t_current = 20.0 
            heater_on = 0 
            indoor_noise = 0.0
            sensor_bias = 0.0
            
            v = r["Volume"]
            sum_ua = r["Sum_UA"]
            
            # Thermal Capacity with 500x multiplier (simulates furniture/walls)
            thermal_cap = RHO * v * CP * 500 
                
            print("\nSimulating Room: {} (Volume: {:.1f}m3)".format(r["Name"], v))
                
            for minute in range(TOTAL_MINUTES):
                current_t_out = t_out_profile[minute]
                
                if t_current <= 20.0:
                    heater_on = 1
                elif t_current >= 22.0:
                    heater_on = 0
                    
                q_heater_room = 95 * v * heater_on
                q_loss = sum_ua * (t_current - current_t_out)
                dT = (DELTA_T / thermal_cap) * (q_heater_room - q_loss)
                t_current += dT
                
                sensor_bias = 0.0
                if 480 <= minute <= 540:
                    sensor_bias = 4.0 * (minute - 480) / 60.0
                elif 540 < minute <= 600:
                    sensor_bias = 4.0 * (600 - minute) / 60.0
                elif 780 <= minute <= 840:
                    sensor_bias = -6.0 * (minute - 780) / 60.0
                elif 840 < minute <= 900:
                    sensor_bias = -6.0 * (900 - minute) / 60.0
                
                indoor_noise = 0.9 * indoor_noise + random.gauss(0, 0.13)
                t_sensor_noisy = t_current + indoor_noise + sensor_bias
                
                if r == results[0]:
                    writer.writerow({
                        'Minute': minute,
                        'T_Out': round(current_t_out, 2),
                        'Heater_Status': heater_on,
                        'T_Indoor_True': round(t_current, 4),
                        'T_Sensor_Noisy': round(t_sensor_noisy, 4)
                    })
                
                if minute % 60 == 0:
                    hour = int(minute / 60)
                    print("  Hour {:02d}:00 | T_out = {:5.2f}C | True Indoor = {:.2f}C | Sensor = {:.2f}C".format(hour, current_t_out, t_current, t_sensor_noisy))

    print("\nSUCCESS: Dataset saved to Desktop as 'Kalman_Dataset.csv'")

# --- Main Execution ---
doc = __revit__.ActiveUIDocument.Document

options = EnergyAnalysisDetailModelOptions()
options.EnergyModelType = EnergyModelType.SpatialElement
options.ExportMullions = False 

t = Transaction(doc, "Generate Energy Model")
t.Start()
energy_model = EnergyAnalysisDetailModel.Create(doc, options)
t.Commit()

spaces = energy_model.GetAnalyticalSpaces()
extracted_results = extract_room_data(doc, spaces)
run_simulation(extracted_results)