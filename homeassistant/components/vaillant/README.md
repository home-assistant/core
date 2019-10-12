# vaillant-component

**Please note that this component is still in beta test**

Add this to your `configuration.yaml`

```yaml
vaillant:
  username: username
  password: password
```

## Created entity
- 1 water_heater, if there is a water heater in your system
- 1 climate per zone (expect if the zone is controlled by room)
- 1 climate per room
- 1 binary_sensor for the circulation
- 1 binary_sensor per room reflecting the state of the "open window" in a room (this is a feature of the vaillant API, if the temperature is going down pretty fast, the API assumes there is an open window and heating stops)
- 1 binary_sensor per room reflecting if the valve is "child locked" or not
- 1 binary_sensor reflecting battery level for each device (VR50, VR51) in the system
- 1 binary_sensor reflecting connectivity for each device (VR50, VR51) in the system
- 1 binary_sensor to know if there is an update pending
- 1 binary_sensor to know if the vr900/920 is connected to the internet
- 1 binary_sensor to know if there is an error at the boiler
- 1 temperature sensor for outdoor temperature
- 1 temperature sensor per zone (expect if the zone is controlled by room)
- 1 temperature sensor per room
- 1 temperature sensor for water_heater
- 1 sensor for water pressure in boiler
- 1 temperature sensor for water temperature in boiler


##Todo's
- remove quick_mode if there is any when setting a new mode ? (creating a new set of services ?)
- tests