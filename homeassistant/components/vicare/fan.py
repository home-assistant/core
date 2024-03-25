"""Demo fan platform that has a fake fan."""
from __future__ import annotations

from contextlib import suppress
import logging
from typing import Any, Optional

from PyViCare.PyViCareDevice import Device as PyViCareDevice
from PyViCare.PyViCareDeviceConfig import PyViCareDeviceConfig
from PyViCare.PyViCareVentilationDevice import VentilationDevice as PyViCareVentilationDevice
from PyViCare.PyViCareUtils import (
    PyViCareInvalidDataError,
    PyViCareNotSupportedFeatureError,
    PyViCareRateLimitError,
)

from requests.exceptions import ConnectionError as RequestConnectionError

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import ordered_list_item_to_percentage, percentage_to_ordered_list_item

from .const import DEVICE_LIST, DOMAIN
from .entity import ViCareEntity
from .types import HeatingProgram, VentilationMode, ViCareDevice

_LOGGER = logging.getLogger(__name__)

ORDERED_NAMED_FAN_SPEEDS = ["levelOne", "levelTwo", "levelThree", "levelFour"]

def _build_entities(
    device_list: list[ViCareDevice],
) -> list[ViCareFan]:
    """Create ViCare fan entities for a device."""

    return [
        ViCareFan(
            device.config,
            device.api,
        )
        for device in device_list
        if isinstance(device.api, PyViCareVentilationDevice)
    ]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the ViCare fan platform."""

    device_list = hass.data[DOMAIN][config_entry.entry_id][DEVICE_LIST]

    async_add_entities(
        await hass.async_add_executor_job(
            _build_entities,
            device_list,
        )
    )


class ViCareFan(ViCareEntity, FanEntity):
    """Representation of the ViCare ventilation device."""

    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        # | FanEntityFeature.PRESET_MODE
    )
    _attributes: dict[str, Any] = {}


    def __init__(
        self,
        device_config: PyViCareDeviceConfig,
        device: PyViCareDevice,
    ) -> None:
        """Initialize the fan device."""
        super().__init__(device_config, device, "ventilator")
        self._attr_translation_key = "ventilator"

    def update(self) -> None:
        """Update state of fan."""
        try:
            with suppress(PyViCareNotSupportedFeatureError):
                self._attributes["active_vicare_mode"] = self._api.getActiveMode()
            with suppress(PyViCareNotSupportedFeatureError):
                self._attributes["active_vicare_program"] = self._api.getActiveProgram()

            self._attributes["vicare_modes"] = self._api.getAvailableModes()
            self._attributes["vicare_programs"] = self._api.getAvailablePrograms()
        except RequestConnectionError:
            _LOGGER.error("Unable to retrieve data from ViCare server")
        except ValueError:
            _LOGGER.error("Unable to decode data from ViCare server")
        except PyViCareRateLimitError as limit_exception:
            _LOGGER.error("Vicare API rate limit exceeded: %s", limit_exception)
        except PyViCareInvalidDataError as invalid_data_exception:
            _LOGGER.error("Invalid data from Vicare server: %s", invalid_data_exception)

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return len(ORDERED_NAMED_FAN_SPEEDS)

    @property
    def percentage(self) -> Optional[int]:
        """Return the current speed percentage."""

        if "active_vicare_program" in self._attributes and self._attributes["active_vicare_program"] in ORDERED_NAMED_FAN_SPEEDS:
            return ordered_list_item_to_percentage(ORDERED_NAMED_FAN_SPEEDS, self._attributes["active_vicare_program"])

        return None

    def set_percentage(self, percentage: int) -> None:
        """Set the speed of the fan, as a percentage."""

        self._api.setPermanentLevel(percentage_to_ordered_list_item(ORDERED_NAMED_FAN_SPEEDS, percentage))

    @property
    def extra_state_attributes(self):
        """Show Device Attributes."""
        return self._attributes
