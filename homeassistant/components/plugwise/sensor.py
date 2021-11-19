"""Plugwise Sensor component for Home Assistant."""
from __future__ import annotations

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import ATTR_ID, ATTR_NAME, ATTR_STATE
from homeassistant.core import callback

from .const import (
    COORDINATOR,
    DOMAIN,
    FW,
    PW_MODEL,
    SMILE,
    VENDOR,
)
from .gateway import SmileGateway
from .models import PW_SENSOR_TYPES, PlugwiseSensorEntityDescription
from .smile_helpers import icon_selector

PARALLEL_UPDATES = 0


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Smile switches from a config entry."""
    # PLACEHOLDER for async_setup_entry_usb()
    return await async_setup_entry_gateway(hass, config_entry, async_add_entities)

async def async_setup_entry_gateway(hass, config_entry, async_add_entities):
    """Set up the Smile sensors from a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id][COORDINATOR]

    entities = []
    for dev_id in coordinator.data[1]:
        for key in coordinator.data[1][dev_id]:
            if key != "sensors":
                continue

            for data in coordinator.data[1][dev_id]["sensors"]:
                for description in PW_SENSOR_TYPES:
                    if (
                        description.plugwise_api == SMILE
                        and description.key == data.get(ATTR_ID)
                    ):
                        entities.extend(
                            [
                                GwSensor(
                                    coordinator,
                                    description,
                                    dev_id,
                                    data,
                                )
                            ]
                        )

    if entities:
        async_add_entities(entities, True)


class GwSensor(SmileGateway, SensorEntity):
    """Representation of a Smile Gateway sensor."""

    def __init__(
        self,
        coordinator,
        description: PlugwiseSensorEntityDescription,
        dev_id,
        sr_data,
    ):
        """Initialise the sensor."""
        _cdata = coordinator.data[1][dev_id]
        super().__init__(
            coordinator,
            description,
            dev_id,
            _cdata.get(PW_MODEL),
            _cdata.get(ATTR_NAME),
            _cdata.get(VENDOR),
            _cdata.get(FW),
        )

        self._attr_name = f"{ _cdata.get(ATTR_NAME)} {description.name}"
        self._attr_native_unit_of_measurement = description.native_unit_of_measurement
        self._attr_native_value = None
        self._attr_should_poll = description.should_poll
        self._attr_unique_id = f"{dev_id}-{description.key}"
        self._attr_state_class = description.state_class
        self._sr_data = sr_data

    @callback
    def _async_process_data(self):
        """Update the entity."""
        self._attr_native_value = self._sr_data.get(ATTR_STATE)
        if self._sr_data.get(ATTR_ID) == "device_state":
            self._attr_icon = icon_selector(self._attr_native_value, None)

        self.async_write_ha_state()

# PLACEHOLDER for class USBSensor()