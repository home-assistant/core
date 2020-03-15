### Installation

Copy this folder to `<config_dir>/custom_components/kostal_plenticore/`.

Add the following to your `configuration.yaml` file:

```yaml
# Example configuration.yaml entry
sensor:
    - platform: kostal_plenticore
      host: <IP>
      password: <Password>
      monitored_conditions:
        - BatteryPercent
        - BatteryCycles
        - HomeGridPower
        - HomeOwnPower
        - HomePVPower
        - HomeBatteryPower
        - HomeGridPower
        - PVPower
        - AutarkyDay
        - AutarkyMonth
        - AutarkyTotal
        - AutarkyYear
        - CO2SavingDay
        - CO2SavingMonth
        - CO2SavingTotal
        - CO2SavingYear
```
