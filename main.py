import os
import csv
import math
import matplotlib.pyplot as plt

# Constants
RHO_AIR = 1.225  # kg/m³
C_P_AIR = 1006   # J/(kg·K)
Q_HVAC = 95.0    # W/m³ (matched to script.py generation)
DT = 60          # seconds

# BIM Parameters
VOLUME = 31.6        # m³
UA = 79.97           # W/K
THERMAL_MASS = 6014021.20  # J/K (Synced to ~155x multiplier)

# Sensor Noise
NOISE_AMPLITUDE = 2.5


def load_data(filename):
    """Load CSV data."""
    outdoor = []
    heater = []
    measured = []
    sensor = []
    
    with open(filename) as f:
        reader = csv.DictReader(f)
        for row in reader:
            outdoor.append(float(row['T_Out']))
            heater.append(int(row['Heater_Status']))
            measured.append(float(row['T_Indoor_True']))
            sensor.append(float(row['T_Sensor_Noisy']))
    
    return outdoor, heater, measured, sensor


def add_noise(true_temps, amplitude):
    """Add Gaussian white noise to temperature readings."""
    import random
    
    noisy = []
    for T in true_temps:
        noise = random.gauss(0, amplitude)
        noisy.append(T + noise)
    
    return noisy


def simulate(outdoor, heater, initial_temp):
    """Simulate room temperature."""
    
    C = RHO_AIR * C_P_AIR * VOLUME + THERMAL_MASS
    
    temps = [initial_temp]
    
    for t_out, h in zip(outdoor, heater):
        T = temps[-1]
        
        Q_loss = UA * (T - t_out)
        Q_gain = Q_HVAC * VOLUME * h
        
        dT = (Q_gain - Q_loss) / C * DT
        
        temps.append(T + dT)
    
    return temps


def kalman_filter(sensor_data, process_variance=0.01, measurement_variance=1.25):
    """
    Simple 1D Kalman filter for temperature smoothing.
    
    process_variance     -> model uncertainty
    measurement_variance -> sensor noise variance
    """
    
    # Initial estimate
    x_est = sensor_data[0]
    
    # Initial estimation error covariance
    P = 1.0
    
    filtered = []
    
    for measurement in sensor_data:
        
        # Prediction step
        x_pred = x_est
        P_pred = P + process_variance
        
        # Kalman gain
        K = P_pred / (P_pred + measurement_variance)
        
        # Update step
        x_est = x_pred + K * (measurement - x_pred)
        P = (1 - K) * P_pred
        
        filtered.append(x_est)
    
    return filtered


def plot(outdoor, simulated, measured, sensor, filtered, heater):
    """Plot results."""
    
    t = range(len(outdoor))
    
    fig, (ax1, ax2, ax3, ax4) = plt.subplots(4, 1, figsize=(14, 11))
    
    # Temperature
    ax1.plot(t, simulated[:-1], 'b-', label='BIM model', lw=2)
    ax1.plot(t, sensor, color='orange', label='Sensor (Noisy)',
             lw=1.2, alpha=0.6)
    ax1.plot(t, filtered, 'g-', label='Kalman Filtered', lw=2)
    ax1.plot(t, outdoor, 'gray', label='Outdoor',
             lw=1, alpha=0.5)
    
    ax1.set_ylabel('Temperature (°C)', fontsize=11)
    ax1.set_title('Room Temperature Estimation & Comfort Index', fontsize=13,
                  fontweight='bold')
    ax1.legend(loc='upper right')
    ax1.grid(True, alpha=0.3)
    
    error = [f - m for f, m in zip(filtered, measured)]
    
    ax2.plot(t, error, 'g-', lw=1.5)
    ax2.axhline(0, color='k', ls='-', lw=0.5)
    ax2.fill_between(t, error, alpha=0.3, color='green')
    
    ax2.set_ylabel('Filtered Error (°C)', fontsize=11)
    ax2.grid(True, alpha=0.3)
    
    # sPMV Comfort Index
    # Simplified assumption: 22°C is optimal comfort (0), with +/- 4°C per PMV unit
    spmv_sensor = [0.25 * s - 5.5 for s in sensor]
    spmv_filtered = [0.25 * f - 5.5 for f in filtered]
    
    ax3.plot(t, spmv_sensor, color='orange', label='Sensor sPMV', lw=1.2, alpha=0.5)
    ax3.plot(t, spmv_filtered, 'g-', label='Filtered sPMV', lw=2)
    ax3.axhline(0, color='k', ls='--', lw=0.8, label='Optimal (0)')
    ax3.axhline(0.5, color='gray', ls=':', lw=0.8)
    ax3.axhline(-0.5, color='gray', ls=':', lw=0.8)
    ax3.set_ylim(-1.5, 1.5)
    
    ax3.set_ylabel('sPMV Index', fontsize=11)
    ax3.legend(loc='upper right')
    ax3.grid(True, alpha=0.3)
    
    # Heater
    ax4.fill_between(t, heater, alpha=0.5,
                     color='orange', step='mid')
    
    ax4.set_ylabel('Heater', fontsize=11)
    ax4.set_xlabel('Time (minutes)', fontsize=11)
    ax4.set_ylim(-0.1, 1.1)
    ax4.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    plt.show()

def plot_zoomed(outdoor, simulated, measured, sensor, filtered, heater, start, end, title, show_truth=False):
    """Plot zoomed section of results."""
    t = range(start, end)
    
    plt.figure(figsize=(10, 5))
    plt.plot(t, simulated[start:end], 'b-', label='BIM model', lw=2)
    if show_truth:
        plt.plot(t, measured[start:end], 'r--', label='Truth', lw=2)
    plt.plot(t, sensor[start:end], color='orange', label='Sensor (Noisy)', lw=1.2, alpha=0.6)
    plt.plot(t, filtered[start:end], 'g-', label='Kalman Filtered', lw=2)
    
    plt.ylabel('Temperature (°C)', fontsize=11)
    plt.xlabel('Time (minutes)', fontsize=11)
    plt.title(title, fontsize=13, fontweight='bold')
    plt.legend(loc='best')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()

def main():
    """Run simulation."""
    
    # Load data
    outdoor, heater, measured, sensor = load_data('Kalman_Dataset.csv')
    
    # Kalman filtering (Balanced tuning)
    filtered = kalman_filter(
        sensor,
        process_variance=0.005,
        measurement_variance=10.0
    )
    
    simulated = simulate(outdoor, heater, measured[0])
    
    avg_sim = sum(simulated[:-1]) / len(measured)
    avg_meas = sum(measured) / len(measured)
    
    rmse_sim = math.sqrt(
        sum((s - m)**2 for s, m in zip(simulated[:-1], measured))
        / len(measured)
    )
    
    rmse_kalman = math.sqrt(
        sum((f - m)**2 for f, m in zip(filtered, measured))
        / len(measured)
    )
    
    print("\n" + "="*60)
    print("THERMAL MODEL RESULTS")
    print("="*60)
    
    print(f"Room: {VOLUME} m³ | UA: {UA} W/K")
    
    print(f"\nAverage Temperatures:")
    print(f"  Simulated:       {avg_sim:.2f} °C")
    print(f"  Measured:        {avg_meas:.2f} °C")
    
    print(f"\nRMSE:")
    print(f"  Simulation RMSE: {rmse_sim:.3f} °C")
    print(f"  Kalman RMSE:     {rmse_kalman:.3f} °C")
    
    print(f"\nTemperature Range:")
    print(f"  Simulated:  {min(simulated):.1f} to {max(simulated):.1f} °C")
    print(f"  Measured:   {min(measured):.1f} to {max(measured):.1f} °C")
    print(f"  Outdoor:    {min(outdoor):.1f} to {max(outdoor):.1f} °C")
    
    print("="*60 + "\n")
    
    # Plot
    plot(outdoor, simulated, measured, sensor, filtered, heater)
    
    # Zoomed Plots
    plot_zoomed(outdoor, simulated, measured, sensor, filtered, heater, 420, 660, "Zoomed: Morning Drift (8:00 - 10:00)", show_truth=False)
    plot_zoomed(outdoor, simulated, measured, sensor, filtered, heater, 780, 960, "Zoomed: Midday No Drift (13:00 - 16:00)", show_truth=False)
    plot_zoomed(outdoor, simulated, measured, sensor, filtered, heater, 1020, 1320, "Zoomed: Evening Drift (18:00 - 21:00)", show_truth=False)


if __name__ == '__main__':
    main()