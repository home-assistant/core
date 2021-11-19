"""Plugwise Binary Sensor component for Home Assistant."""
from __future__ import annotations

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import ATTR_ID, ATTR_NAME
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
from .models import PW_BINARY_SENSOR_TYPES, PlugwiseBinarySensorEntityDescription
from .smile_helpers import GWBinarySensor

PARALLEL_UPDATES = 0


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Smile switches from a config entry."""
    # # PLACEHOLDER USB entry setup
    return await async_setup_entry_gateway(hass, config_entry, async_add_entities)

async def async_setup_entry_gateway(hass, config_entry, async_add_entities):
    """Set up the Smile binary_sensors from a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id][COORDINATOR]

    entities = []
    for dev_id in coordinator.data[1]:
        for key in coordinator.data[1][dev_id]:
            if key != "binary_sensors":
                continue

            for data in coordinator.data[1][dev_id]["binary_sensors"]:
                for description in PW_BINARY_SENSOR_TYPES:
                    if (
                        description.plugwise_api == SMILE
                        and description.key == data.get(ATTR_ID)
                    ):
                        entities.extend(
                            [
                                GwBinarySensor(
                                    coordinator,
                                    description,
                                    dev_id,
                                    data,
                                )
                            ]
                        )

    if entities:
        async_add_entities(entities, True)


class GwBinarySensor(SmileGateway, BinarySensorEntity):
    """Representation of a Gateway binary_sensor."""

    def __init__(
        self,
        coordinator,
        description: PlugwiseBinarySensorEntityDescription,
        dev_id,
        bs_data,
    ):
        """Initialise the binary_sensor."""
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

        self._gw_b_sensor = GWBinarySensor(
            coordinator.data, dev_id, bs_data.get(ATTR_ID)
        )

        self._attr_entity_registry_enabled_default = (
            description.entity_registry_enabled_default
        )
        self._attr_extra_state_attributes = None
        self._attr_icon = None
        self._attr_is_on = False
        self._attr_name = f"{_cdata.get(ATTR_NAME)} {description.name}"
        self._attr_should_poll = self.entity_description.should_poll
        self._attr_unique_id = f"{dev_id}-{description.key}"

    @callback
    def _async_process_data(self):
        """Update the entity."""
        self._gw_b_sensor.update_data()
        self._attr_extra_state_attributes = self._gw_b_sensor.extra_state_attributes
        self._attr_icon = self._gw_b_sensor.icon
        self._attr_is_on = self._gw_b_sensor.is_on

        if self._gw_b_sensor.notification:
            for notify_id, message in self._gw_b_sensor.notification.items():
                self.hass.components.persistent_notification.async_create(
                    message, "Plugwise Notification:", f"{DOMAIN}.{notify_id}"
                )

        self.async_write_ha_state()

# PLACEHOLDER for class USBBinarySensor()