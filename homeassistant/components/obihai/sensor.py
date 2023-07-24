"""Support for Obihai Sensors."""
from __future__ import annotations

from abc import ABC, abstractmethod
import datetime

from requests.exceptions import RequestException

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .connectivity import ObihaiConnection
from .const import DOMAIN, LOGGER
from .entity import ObihaiEntity

SCAN_INTERVAL = datetime.timedelta(seconds=5)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Obihai sensor entries."""

    requester: ObihaiConnection = hass.data[DOMAIN][entry.entry_id]

    sensors: list[ObihaiEntity] = []
    for key in requester.services:
        sensors.append(ObihaiServiceSensor(requester, key))

    if requester.line_services is not None:
        for key in requester.line_services:
            sensors.append(ObihaiLineServiceSensor(requester, key))

    for key in requester.call_direction:
        sensors.append(ObihaiCallDirectionSensor(requester, key))

    async_add_entities(sensors, update_before_add=True)


class ObihaiSensor(ObihaiEntity, SensorEntity, ABC):
    """Generic Obihai Sensor."""

    @abstractmethod
    def _update(self) -> None:
        """Child class will override with sensor specific tasks."""

    def update(self) -> None:
        """Update the sensor."""

        LOGGER.debug("Running update on %s", self._service_name)
        try:
            self._update()

            if not self.requester.available:
                self.requester.available = True
                LOGGER.info("Connection restored")
            self._attr_available = True

            return

        except RequestException as exc:
            if self.requester.available:
                LOGGER.warning("Connection failed, Obihai offline? %s", exc)
        except IndexError as exc:
            if self.requester.available:
                LOGGER.warning("Connection failed, bad response: %s", exc)

        self._attr_native_value = None
        self._attr_available = False
        self.requester.available = False


class ObihaiCallDirectionSensor(ObihaiSensor):
    """Call Direction sensor."""

    @property
    def icon(self) -> str:
        """Return an icon."""

        if self._attr_native_value == "No Active Calls":
            return "mdi:phone-off"
        if self._attr_native_value == "Inbound Call":
            return "mdi:phone-incoming"
        return "mdi:phone-outgoing"

    def _update(self) -> None:
        """Update the sensor."""
        call_direction = self._pyobihai.get_call_direction()

        if self._service_name in call_direction:
            self._attr_native_value = call_direction.get(self._service_name)


class ObihaiLineServiceSensor(ObihaiSensor):
    """PHONE1 Port/PHONE1 Port last caller info sensors."""

    @property
    def icon(self) -> str:
        """Return an icon."""

        if "Caller Info" in self._service_name:
            return "mdi:phone-log"
        if self._attr_native_value == "Ringing":
            return "mdi:phone-ring"
        if self._attr_native_value == "Off Hook":
            return "mdi:phone-in-talk"
        return "mdi:phone-hangup"

    def _update(self) -> None:
        """Update the sensor."""

        services = self._pyobihai.get_line_state()

        if services is not None and self._service_name in services:
            self._attr_native_value = services.get(self._service_name)


class ObihaiServiceSensor(ObihaiSensor):
    """Reboot Required/Last Reboot/SP Service Status/OBiTALK Service Status sensors."""

    def __init__(self, requester: ObihaiConnection, service_name: str) -> None:
        """Initialize monitor sensor."""

        super().__init__(requester, service_name)

        if self._service_name == "Last Reboot":
            self._attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def icon(self) -> str:
        """Return an icon."""

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

    def _update(self) -> None:
        """Update the sensor."""

        services = self._pyobihai.get_state()

        if self._service_name in services:
            self._attr_native_value = services.get(self._service_name)
