"""Plugwise Binary Sensor component for Home Assistant."""

import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import callback

from .const import (
    COORDINATOR,
    DOMAIN,
    FLAME_ICON,
    FLOW_OFF_ICON,
    FLOW_ON_ICON,
    IDLE_ICON,
    NO_NOTIFICATION_ICON,
    NOTIFICATION_ICON,
)
from .gateway import SmileGateway

BINARY_SENSOR_MAP = {
    "dhw_state": ["Domestic Hot Water State", None],
    "slave_boiler_state": ["Secondary Heater Device State", None],
}
SEVERITIES = ["other", "info", "warning", "error"]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Smile binary_sensors from a config entry."""
    api = hass.data[DOMAIN][config_entry.entry_id]["api"]
    coordinator = hass.data[DOMAIN][config_entry.entry_id][COORDINATOR]

    entities = []
    is_thermostat = api.single_master_thermostat()

    all_devices = api.get_all_devices()
    for dev_id, device_properties in all_devices.items():

        if device_properties["class"] == "heater_central":
            data = api.get_device_data(dev_id)
            for binary_sensor in BINARY_SENSOR_MAP:
                if binary_sensor not in data:
                    continue

                entities.append(
                    PwBinarySensor(
                        api,
                        coordinator,
                        device_properties["name"],
                        dev_id,
                        binary_sensor,
                    )
                )

        if device_properties["class"] == "gateway" and is_thermostat is not None:
            entities.append(
                PwNotifySensor(
                    api,
                    coordinator,
                    device_properties["name"],
                    dev_id,
                    "plugwise_notification",
                )
            )

    async_add_entities(entities, True)


class SmileBinarySensor(SmileGateway):
    """Represent Smile Binary Sensors."""

    def __init__(self, api, coordinator, name, dev_id, binary_sensor):
        """Initialise the binary_sensor."""
        super().__init__(api, coordinator, name, dev_id)

        self._binary_sensor = binary_sensor

        self._icon = None
        self._is_on = False

        if dev_id == self._api.heater_id:
            self._entity_name = "Auxiliary"

        sensorname = binary_sensor.replace("_", " ").title()
        self._name = f"{self._entity_name} {sensorname}"

        if dev_id == self._api.gateway_id:
            self._entity_name = f"Smile {self._entity_name}"

        self._unique_id = f"{dev_id}-{binary_sensor}"

    @property
    def icon(self):
        """Return the icon of this entity."""
        return self._icon

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._is_on

    @callback
    def _async_process_data(self):
        """Update the entity."""
        raise NotImplementedError


class PwBinarySensor(SmileBinarySensor, BinarySensorEntity):
    """Representation of a Plugwise binary_sensor."""

    @callback
    def _async_process_data(self):
        """Update the entity."""
        data = self._api.get_device_data(self._dev_id)

        if not data:
            _LOGGER.error("Received no data for device %s", self._binary_sensor)
            self.async_write_ha_state()
            return

        if self._binary_sensor not in data:
            self.async_write_ha_state()
            return

        self._is_on = data[self._binary_sensor]

        if self._binary_sensor == "dhw_state":
            self._icon = FLOW_ON_ICON if self._is_on else FLOW_OFF_ICON
        if self._binary_sensor == "slave_boiler_state":
            self._icon = FLAME_ICON if self._is_on else IDLE_ICON

        self.async_write_ha_state()


class PwNotifySensor(SmileBinarySensor, BinarySensorEntity):
    """Representation of a Plugwise Notification binary_sensor."""

    def __init__(self, api, coordinator, name, dev_id, binary_sensor):
        """Set up the Plugwise API."""
        super().__init__(api, coordinator, name, dev_id, binary_sensor)

        self._attributes = {}

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    @callback
    def _async_process_data(self):
        """Update the entity."""
        notify = self._api.notifications

        for severity in SEVERITIES:
            self._attributes[f"{severity}_msg"] = []

        self._is_on = False
        self._icon = NO_NOTIFICATION_ICON

        if notify:
            self._is_on = True
            self._icon = NOTIFICATION_ICON

            for details in notify.values():
                for msg_type, msg in details.items():
                    if msg_type not in SEVERITIES:
                        msg_type = "other"

                    self._attributes[f"{msg_type.lower()}_msg"].append(msg)

        self.async_write_ha_state()
