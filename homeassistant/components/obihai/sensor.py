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
        self._state = None
        self._name = f"{OBIHAI} {self._service_name}"
        self._pyobihai = pyobihai
        self._unique_id = f"{serial}-{self._service_name}"

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def available(self):
        """Return if sensor is available."""
        if self._state is not None:
            return True
        return False

    @property
    def unique_id(self):
        """Return the unique ID."""
        return self._unique_id

    @property
    def device_class(self):
        """Return the device class for uptime sensor."""
        if self._service_name == "Last Reboot":
            return SensorDeviceClass.TIMESTAMP
        return None

    @property
    def icon(self):
        """Return an icon."""
        if self._service_name == "Call Direction":
            if self._state == "No Active Calls":
                return "mdi:phone-off"
            if self._state == "Inbound Call":
                return "mdi:phone-incoming"
            return "mdi:phone-outgoing"
        if "Caller Info" in self._service_name:
            return "mdi:phone-log"
        if "Port" in self._service_name:
            if self._state == "Ringing":
                return "mdi:phone-ring"
            if self._state == "Off Hook":
                return "mdi:phone-in-talk"
            return "mdi:phone-hangup"
        if "Service Status" in self._service_name:
            if "OBiTALK Service Status" in self._service_name:
                return "mdi:phone-check"
            if self._state == "0":
                return "mdi:phone-hangup"
            return "mdi:phone-in-talk"
        if "Reboot Required" in self._service_name:
            if self._state == "false":
                return "mdi:restart-off"
            return "mdi:restart-alert"
        return "mdi:phone"

    def update(self) -> None:
        """Update the sensor."""
        if not self._pyobihai.check_account():
            self._state = None
            return

        services = self._pyobihai.get_state()

        if self._service_name in services:
            self._state = services.get(self._service_name)

        services = self._pyobihai.get_line_state()

        if services is not None and self._service_name in services:
            self._state = services.get(self._service_name)

        call_direction = self._pyobihai.get_call_direction()

        if self._service_name in call_direction:
            self._state = call_direction.get(self._service_name)
