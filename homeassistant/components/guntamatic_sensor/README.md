# Guntamatic Sensor

## High-Level Description
The Guntamatic Sensor integration allows Home Assistant to monitor sensors from Guntamatic heaters. Guntamatic is a brand of modern wood/pellet gas boilers. This integration exposes temperature, operational state, and other relevant sensors.


## Sensors
The integration currently exposes the following sensors (dynamic values):

- Boiler state: Running, STANDBY
- Boiler temperature
- Outside temperature
- Buffer load and buffer top/mid/bottom temperatures
- Boiler shunt pump, suction fan, primary and secondary air
- CO₂ content
- Domestic hot water (DHW) temperatures and pumps
- Heating circulation pumps and flow temperatures for multiple zones
- Program states (HEAT/HC)
- Interruptions
- Serial number, version, operation time, service hours
- Auxiliary pumps
- Additional WW/Buffer sensors

## Installation Instructions
1. Copy the `guntamatic_sensor` folder into `config/custom_components/`.
2. Restart Home Assistant.
3. Go to **Settings → Devices & Services → Add Integration**.
4. Search for "Guntamatic Sensor" and enter the host address of your heater.

## Removal Instructions
1. Go to **Settings → Devices & Services**.
2. Select the Guntamatic Sensor integration.
3. Click **Delete** to remove the integration and its entities.
4. Optional: Delete the `guntamatic_sensor` folder from `custom_components/`.

## Services
This integration does **not** provide any Home Assistant service calls.

