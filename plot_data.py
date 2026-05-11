import pandas as pd
import matplotlib.pyplot as plt
import os

desktop_path = os.path.join(os.path.expanduser("~"), "Desktop", "Kalman_Dataset.csv")

if not os.path.exists(desktop_path):
    print("Dataset not found at:", desktop_path)
    print("Please run the Revit pyRevit script first to generate the data.")
    exit()

df = pd.read_csv(desktop_path)

# Convert Minute to Hours for the x-axis
df['Hour'] = df['Minute'] / 60

# Create the plot
plt.figure(figsize=(12, 6))

# Plot Outdoor Temperature
plt.plot(df['Hour'], df['T_Out'], label='T_Out (Outdoor)', color='blue', linestyle='--')

# Plot True Indoor Temperature
plt.plot(df['Hour'], df['T_Indoor_True'], label='T_Indoor_True', color='green', linewidth=2)

# Plot Noisy Sensor Temperature
plt.scatter(df['Hour'], df['T_Sensor_Noisy'], label='T_Sensor_Noisy', color='red', s=5, alpha=0.5)

# Plot Heater Status efficiently by shading the background when it is ON
ax = plt.gca()
ax.fill_between(df['Hour'], 0, 1, where=(df['Heater_Status'] == 1), 
                color='orange', alpha=0.15, transform=ax.get_xaxis_transform(), 
                step='post', label='Heater ON')

plt.title('24-Hour Temperature Prediction & Sensor Data')
plt.xlabel('Time (Hours)')
plt.ylabel('Temperature (°C)')
plt.xlim(0, 24)
plt.xticks(range(0, 25, 2))
plt.grid(True, linestyle=':', alpha=0.6)

plt.legend(loc='center right')

plt.tight_layout()
plt.show()