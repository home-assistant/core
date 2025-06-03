"""Support for Obihai Sensors."""

from __future__ import annotations

import datetime

from requests.exceptions import RequestException

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .connectivity import ObihaiConnection
from .const import DOMAIN, LOGGER, OBIHAI

SCAN_INTERVAL = datetime.timedelta(seconds=5)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Obihai sensor entries."""

    requester: ObihaiConnection = hass.data[DOMAIN][entry.entry_id]

    sensors = [ObihaiServiceSensors(requester, key) for key in requester.services]

    sensors.extend(
        ObihaiServiceSensors(requester, key) for key in requester.call_direction
    )

    if requester.line_services is not None:
        sensors.extend(
            ObihaiServiceSensors(requester, key) for key in requester.line_services
        )

    async_add_entities(sensors, update_before_add=True)


class ObihaiServiceSensors(SensorEntity):
    """Get the status of each Obihai Lines."""

    def __init__(self, requester: ObihaiConnection, service_name: str) -> None:
        """Initialize monitor sensor."""

        self.requester = requester
        self._service_name = service_name
        self._attr_name = f"{OBIHAI} {self._service_name}"
        self._pyobihai = requester.pyobihai
        self._attr_unique_id = f"{requester.serial}-{self._service_name}"
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

        LOGGER.debug("Running update on %s", self._service_name)
        try:
            # port connection, and last caller info
            if "Caller Info" in self._service_name or "Port" in self._service_name:
                services = self._pyobihai.get_line_state()

                if services is not None and self._service_name in services:
                    self._attr_native_value = services.get(self._service_name)
            elif self._service_name == "Call Direction":
                call_direction = self._pyobihai.get_call_direction()

                if self._service_name in call_direction:
                    self._attr_native_value = call_direction.get(self._service_name)
            else:  # SIP Profile service sensors, phone sensor, and last reboot
                services = self._pyobihai.get_state()

                if self._service_name in services:
                    self._attr_native_value = services.get(self._service_name)

            if not self.requester.available:
                self.requester.available = True
                LOGGER.warning("Connection restored")
            self._attr_available = True

        except RequestException as exc:
            if self.requester.available:
                LOGGER.warning("Connection failed, Obihai offline? %s", exc)
            self._attr_native_value = None
            self._attr_available = False
            self.requester.available = False
        except IndexError as exc:
            if self.requester.available:
                LOGGER.warning("Connection failed, bad response: %s", exc)
            self._attr_native_value = None
            self._attr_available = False
            self.requester.available = False
