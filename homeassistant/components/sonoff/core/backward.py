"""Why Hass v2021.12 minimal?

- v2021.7 - new Entity attributes style
- v2021.8 - new electric unit_of_measurement
- v2021.9 - new SensorEntity native_value and native_unit_of_measurement
- v2021.12 - new EntityCategory class (isinstance check in v2022.4)
- v2021.12 - new ButtonEntity
- v2021.12 - new FanEntity percentage logic
- v2021.12 - new SensorDeviceClass, SensorStateClass classes
"""
from homeassistant.const import MAJOR_VERSION, MINOR_VERSION

hass_version_supported = (MAJOR_VERSION, MINOR_VERSION) >= (2021, 12)
