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

    _attr_preset_modes = list[str](
        [
            VentilationMode.PERMANENT,
            VentilationMode.VENTILATION,
            VentilationMode.SENSOR_DRIVEN,
            VentilationMode.SENSOR_OVERRIDE,
        ]
    )
    _attr_speed_count = len(ORDERED_NAMED_FAN_SPEEDS)
    _attr_supported_features = FanEntityFeature.SET_SPEED | FanEntityFeature.PRESET_MODE

    def __init__(
        self,
        device_config: PyViCareDeviceConfig,
        device: PyViCareDevice,
        translation_key: str,
    ) -> None:
        """Initialize the fan entity."""
        super().__init__(device_config, device, translation_key)
        self._attr_translation_key = translation_key

    def update(self) -> None:
        """Update state of fan."""
        try:
            with suppress(PyViCareNotSupportedFeatureError):
                self._attr_preset_mode = VentilationMode.to_ha_mode(
                    self._api.getActiveMode()
                )
            with suppress(PyViCareNotSupportedFeatureError):
                self._attr_percentage = ordered_list_item_to_percentage(
                    ORDERED_NAMED_FAN_SPEEDS, self._api.getActiveProgram()
                )
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

    def set_percentage(self, percentage: int) -> None:
        """Set the speed of the fan, as a percentage."""
        if VentilationMode.from_ha_mode(self._attr_preset_mode) != str(
            VentilationMode.PERMANENT
        ):
            _LOGGER.debug("changing ventilation mode to %s", VentilationMode.PERMANENT)
            self._api.setActiveMode(VentilationMode.PERMANENT)

        level = percentage_to_ordered_list_item(ORDERED_NAMED_FAN_SPEEDS, percentage)
        _LOGGER.debug("changing ventilation level to %s", level)
        self._api.setPermanentLevel(level)

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        target_mode = VentilationMode.from_ha_mode(self._attr_preset_mode)
        _LOGGER.debug("changing ventilation mode to %s", target_mode)
        self._api.setActiveMode(target_mode)
