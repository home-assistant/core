"""Support for hive water heaters."""
from homeassistant.const import TEMP_CELSIUS

from homeassistant.components.water_heater import (
    STATE_ECO, STATE_ON, STATE_OFF, SUPPORT_OPERATION_MODE, WaterHeaterDevice)

from . import DATA_HIVE, DOMAIN

SUPPORT_FLAGS_HEATER = (SUPPORT_OPERATION_MODE)

HIVE_TO_HASS_STATE = {
    'SCHEDULE': STATE_ECO,
    'ON': STATE_ON,
    'OFF': STATE_OFF,
}

HASS_TO_HIVE_STATE = {
    STATE_ECO: 'SCHEDULE',
    STATE_ON: 'ON',
    STATE_OFF: 'OFF',
}

SUPPORT_WATER_HEATER = [STATE_ECO, STATE_ON, STATE_OFF]


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Wink water heater devices."""
    if discovery_info is None:
        return
    if discovery_info["HA_DeviceType"] != "HotWater":
        return

    session = hass.data.get(DATA_HIVE)
    water_heater = HiveWaterHeater(session, discovery_info)

    add_entities([water_heater])
    session.entities.append(water_heater)
