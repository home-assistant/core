"""Support for Obihai Sensors."""
from __future__ import annotations

from datetime import timedelta

from pyobihai import PyObihai

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .connectivity import ObihaiConnection
from .const import OBIHAI

SCAN_INTERVAL = timedelta(seconds=5)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Obihai sensor entries."""

    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    host = entry.data[CONF_HOST]
    requester = ObihaiConnection(host, username, password)

    await hass.async_add_executor_job(requester.update)
    sensors = []
    for key in requester.services:
        sensors.append(ObihaiServiceSensors(requester.pyobihai, requester.serial, key))

    if requester.line_services is not None:
        for key in requester.line_services:
            sensors.append(
                ObihaiServiceSensors(requester.pyobihai, requester.serial, key)
            )

    for key in requester.call_direction:
        sensors.append(ObihaiServiceSensors(requester.pyobihai, requester.serial, key))

    async_add_entities(sensors, update_before_add=True)


class ObihaiServiceSensors(SensorEntity):
    """Get the status of each Obihai Lines."""

    def __init__(self, pyobihai: PyObihai, serial: str, service_name: str) -> None:
        """Initialize monitor sensor."""
        self._service_name = service_name
        self._attr_name = f"{OBIHAI} {self._service_name}"
        self._pyobihai = pyobihai
        self._attr_unique_id = f"{serial}-{self._service_name}"
        if self._service_name == "Last Reboot":
            self._attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def icon(self) -> str:
        """Return an icon."""
        if self._service_name == "Call Direction":
            if self._attr_native_value == "No Active Calls":
                return "mdi:phone-off"
            if self._attr_native_value == "Inbound Call":
                return "mdi:phone-incoming"
            return "mdi:phone-outgoing"
        if "Caller Info" in self._service_name:
            return "mdi:phone-log"
        if "Port" in self._service_name:
            if self._attr_native_value == "Ringing":
                return "mdi:phone-ring"
            if self._attr_native_value == "Off Hook":
                return "mdi:phone-in-talk"
            return "mdi:phone-hangup"
        if "Service Status" in self._service_name:
            if "OBiTALK Service Status" in self._service_name:
                return "mdi:phone-check"
            if self._attr_native_value == "0":
                return "mdi:phone-hangup"
            return "mdi:phone-in-talk"
        if "Reboot Required" in self._service_name:
            if self._attr_native_value == "false":
                return "mdi:restart-off"
            return "mdi:restart-alert"
        return "mdi:phone"

    def update(self) -> None:
        """Update the sensor."""
        if not self._pyobihai.check_account():
            self._attr_native_value = None
            self._attr_available = False
            return

        services = self._pyobihai.get_state()

        if self._service_name in services:
            self._attr_native_value = services.get(self._service_name)

        services = self._pyobihai.get_line_state()

        if services is not None and self._service_name in services:
            self._attr_native_value = services.get(self._service_name)

        call_direction = self._pyobihai.get_call_direction()

        if self._service_name in call_direction:
            self._attr_native_value = call_direction.get(self._service_name)

        if self._attr_native_value is None:
            self._attr_available = False
        self._attr_available = True
