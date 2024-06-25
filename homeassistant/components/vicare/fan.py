"""Viessmann ViCare ventilation device."""

from __future__ import annotations

from contextlib import suppress
import logging
from typing import Any

from PyViCare.PyViCareDevice import Device as PyViCareDevice
from PyViCare.PyViCareDeviceConfig import PyViCareDeviceConfig
from PyViCare.PyViCareUtils import (
    PyViCareInvalidDataError,
    PyViCareNotSupportedFeatureError,
    PyViCareRateLimitError,
)
from PyViCare.PyViCareVentilationDevice import (
    VentilationDevice as PyViCareVentilationDevice,
)
from requests.exceptions import ConnectionError as RequestConnectionError

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)

from .const import DEVICE_LIST, DOMAIN
from .entity import ViCareEntity
from .types import VentilationMode, VentilationProgram, ViCareDevice

_LOGGER = logging.getLogger(__name__)

ORDERED_NAMED_FAN_SPEEDS = [
    VentilationProgram.LEVEL_ONE,
    VentilationProgram.LEVEL_TWO,
    VentilationProgram.LEVEL_THREE,
    VentilationProgram.LEVEL_FOUR,
]

PRESET_MODES = [
    VentilationMode.PERMANENT,
    VentilationMode.VENTILATION,
    VentilationMode.SENSOR_DRIVEN,
    VentilationMode.SENSOR_OVERRIDE,
]


def _build_entities(
    device_list: list[ViCareDevice],
) -> list[ViCareFan]:
    """Create ViCare fan entities for a device."""

    return [
        ViCareFan(device.config, device.api, "ventilation")
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

    _attr_speed_count = len(ORDERED_NAMED_FAN_SPEEDS)
    _attr_supported_features = FanEntityFeature.SET_SPEED | FanEntityFeature.PRESET_MODE
    _attributes: dict[str, Any] = {
        "active_vicare_mode": None,
        "active_vicare_program": None,
        "vicare_modes": None,
        "vicare_programs": None,
    }

    def __init__(
        self,
        device_config: PyViCareDeviceConfig,
        device: PyViCareDevice,
        translation_key: str,
    ) -> None:
        """Initialize the fan entity."""
        super().__init__(device_config, device, translation_key)
        self._attr_translation_key = translation_key

        with suppress(PyViCareNotSupportedFeatureError):
            self._attributes["vicare_modes"] = self._api.getAvailableModes()
        self._attributes["vicare_programs"] = self._api.getAvailablePrograms()

    def update(self) -> None:
        """Update state of fan."""
        try:
            with suppress(PyViCareNotSupportedFeatureError):
                self._attributes["active_vicare_mode"] = self._api.getActiveMode()
            with suppress(PyViCareNotSupportedFeatureError):
                self._attributes["active_vicare_program"] = self._api.getActiveProgram()
        except RequestConnectionError:
            _LOGGER.error("Unable to retrieve data from ViCare server")
        except ValueError:
            _LOGGER.error("Unable to decode data from ViCare server")
        except PyViCareRateLimitError as limit_exception:
            _LOGGER.error("Vicare API rate limit exceeded: %s", limit_exception)
        except PyViCareInvalidDataError as invalid_data_exception:
            _LOGGER.error("Invalid data from Vicare server: %s", invalid_data_exception)

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="fan_must_be_on",
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if the entity is on."""
        # Viessmann ventilation unit cannot be turned off
        return True

    @property
    def percentage(self) -> int | None:
        """Return the current speed percentage."""
        return ordered_list_item_to_percentage(
            ORDERED_NAMED_FAN_SPEEDS, self._attributes["active_vicare_program"]
        )

    def set_percentage(self, percentage: int) -> None:
        """Set the speed of the fan, as a percentage."""

        if self._attributes["active_vicare_mode"] is not str(VentilationMode.PERMANENT):
            self.set_preset_mode(VentilationMode.PERMANENT)

        level = percentage_to_ordered_list_item(ORDERED_NAMED_FAN_SPEEDS, percentage)
        _LOGGER.debug("changing ventilation level to %s", level)
        self._api.setPermanentLevel(level)

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode, e.g., auto, smart, interval, favorite."""

        return self._attributes["active_vicare_mode"]

    @property
    def preset_modes(self) -> list[str] | None:
        """Return a list of available preset modes."""
        return list[str](PRESET_MODES)

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        _LOGGER.debug("changing ventilation mode to %s", preset_mode)
        self._api.setActiveMode(preset_mode)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Show Device Attributes."""
        return self._attributes
