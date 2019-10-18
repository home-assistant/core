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
- tests:
    - zone: set mode while quick mode (not for zone) is running
    - zone: set mode while quick mode (for zone) is running
    - zone: set mode while quick veto is running
    - zone: set low temp when AUTO
    - zone: set high temp when AUTO
    - zone: set target temp
    - room: set mode while quick mode (not for room) is running
    - room: set mode while quick mode (for room) is running
    - room: set mode while quick veto is running
    - room: set target temp
    - binary_sensor system error
     