"""Platform for sensor integration."""

from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import SUN_EVENT_SUNRISE, SUN_EVENT_SUNSET
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.sun import get_astral_event_date
from homeassistant.util import dt as dt_util
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import async_get_platforms
from homeassistant.helpers.event import async_track_state_change
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.restore_state import RestoreEntity

from random import uniform

from .const import DOMAIN, NAME

_LOGGER = logging.getLogger(__name__)

class VirtualPowerSensor(SensorEntity, RestoreEntity):
    """Representation of a Virtual Power Sensor."""

    # Device Type	Approx. Wattage
    # LED Bulb	5 - 15 W
    # Incandescent Bulb	40 - 100 W
    # Smart Plug (idle)	1 - 2 W
    # Ceiling Fan	50 - 75 W
    # Laptop Charger	30 - 60 W
    # Desktop Computer	100 - 250 W
    # TV (LED/LCD)	50 - 150 W
    # Refrigerator	100 - 800 W
    # Air Conditioner	1,000 - 2,500 W
    # Heater	1,000 - 1,500 W
    # Router	5 - 15

    def __init__(self, hass: HomeAssistant, entity_id: str, watts: float):
        self.hass = hass
        self._entity_id = entity_id

        self._attr_device_class = SensorDeviceClass.POWER

        name = entity_id.split(".")[-1]
        self._attr_name = f"{name}_virtual_power"
        self._attr_unique_id = f"virtual_power_{name}"
        self._state = 0.0  # Default power usage in watts
        self._watts = watts

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._attr_name

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._attr_unique_id

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_info(self):
        """Return information about the device."""
        return {
            "identifiers": {(DOMAIN, NAME)},
            "name": NAME,
            "manufacturer": NAME,
        }

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return "W"

    @callback
    def update_virtual_power(self):
        """Update the power consumption based on the linked entity's state."""
        state = self.hass.states.get(self._entity_id)

        _LOGGER.debug(("Sensor %s state: %s", self._entity_id, state))
        
        if state:
            # Example logic: if the device is 'on', use 50W; otherwise, 0W
            self._state = self._watts if state.state == "on" else 0.0
            print(f"Entity: {self._entity_id}, State: {state.state}, Power: {self._state}W")
            self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Register callbacks when the sensor is added to Home Assistant."""
        async_track_state_change(
            self.hass, [self._entity_id], lambda *_: self.update_virtual_power()
        )
        self.update_virtual_power()

    async def async_added_to_hass(self):
        """Restore previous state when entity is added."""
        await super().async_added_to_hass()

        if (last_state := await self.async_get_last_state()) is not None:
            self._state = last_state.state    

class VirtualPowerSensorAlwaysOn(SensorEntity, RestoreEntity):
    """Representation of a Virtual Power Sensor."""

    def __init__(self, hass: HomeAssistant, entity_id: str, watts: float):
        self.hass = hass
        self._entity_id = entity_id
        self._attr_name = f"{entity_id}_virtual_power"
        self._attr_unique_id = f"virtual_power_{entity_id}"
        self._state = watts  # Default power usage in watts
        self._watts = watts

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._attr_name

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._attr_unique_id

    @property
    def device_info(self):
        """Return information about the device."""
        return {
            "identifiers": {(DOMAIN, NAME)},
            "name": NAME,
            "manufacturer": NAME,
        }

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return "W"

    @callback
    def update_virtual_power(self):
        """Update the power consumption based on the linked entity's state."""
    
        self._state = self._watts
        # self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Register callbacks when the sensor is added to Home Assistant."""
        async_track_state_change(
            self.hass, [self._entity_id], lambda *_: self.update_virtual_power()
        )
        self.update_virtual_power()

    async def async_added_to_hass(self):
        """Restore previous state when entity is added."""
        await super().async_added_to_hass()

        if (last_state := await self.async_get_last_state()) is not None:
            self._state = last_state.state    

class FakeDeviceVirtualPowerSensor(SensorEntity, RestoreEntity):
    """Representation of a fake device virtual power sensor."""

    def __init__(self, device_type: str, min_wattage: float, max_wattage: float):
        """Initialize the virtual power sensor."""
        self._device_type = device_type
        self._min_wattage = min_wattage
        self._max_wattage = max_wattage
        entity_id = f"sensor.{device_type.lower().replace(' ', '_')}_power"
        self._entity_id = entity_id
        self._attr_name = f"{entity_id}_virtual_power"
        self._attr_unique_id = f"virtual_power_{entity_id}"
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._device_type} Power"

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._attr_unique_id

    @property
    def device_info(self):
        """Return information about the device."""
        return {
            "identifiers": {(DOMAIN, NAME)},
            "name": NAME,
            "manufacturer": NAME,
        }

    @property
    def state(self):
        """Return the current power usage."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return "W"

    def update(self):
        """Simulate a power usage value."""
        self._state = round(uniform(self._min_wattage, self._max_wattage), 2)

    async def async_added_to_hass(self):
        """Restore previous state when entity is added."""
        await super().async_added_to_hass()

        if (last_state := await self.async_get_last_state()) is not None:
            self._state = last_state.state    

class TotalEnergySensor(SensorEntity, RestoreEntity):
    """Representation of a total energy sensor."""

    def __init__(self, hass: HomeAssistant):
        """Initialize the total energy sensor."""
        self._hass = hass
        self._state = None
        entity_id = f"sensor.total_energy_usage"
        self._entity_id = entity_id
        self._attr_name = f"{entity_id}_energyr"
        self._attr_unique_id = f"power_{entity_id}"

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Total Energy Usage"

    @property
    def device_info(self):
        """Return information about the device."""
        return {
            "identifiers": {(DOMAIN, NAME)},
            "name": NAME,
            "manufacturer": NAME,
        }

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._attr_unique_id

    @property
    def state(self):
        """Return the total energy usage in kWh."""
        return self._state

    @property
    def device_class(self) -> str:
        """Return the device_class of the sensor."""
        return "energy"

    @property
    def state_class(self) -> str:
        """Return the state_class of the sensor."""
        return "total"

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return "kWh"

    def update(self):
        """Calculate the total energy usage from all power sensors."""

        registry = er.async_get(self.hass)

        entities = [
            entry
            for entry in registry.entities.values()
            if entry.domain == "sensor" and entry.entity_id.endswith("_power")
        ]

        total_watts = 0

        if entities is not None:
            for entity_id in [entity.entity_id for entity in entities]:
                state = self._hass.states.get(entity_id)
                if state and state.state not in (None, "unknown"):
                    try:
                        total_watts += float(state.state)
                    except ValueError:
                        continue

        # Convert watts to kilowatts and calculate energy usage
        self._state = round(total_watts / 1000, 2)


    async def async_added_to_hass(self):
        """Restore previous state when entity is added."""
        await super().async_added_to_hass()

        if (last_state := await self.async_get_last_state()) is not None:
            self._state = last_state.state