"""Viessmann ViCare ventilation device."""

from __future__ import annotations

from contextlib import suppress
import enum
import logging
from typing import Any

from PyViCare.PyViCareDevice import Device as PyViCareDevice
from PyViCare.PyViCareDeviceConfig import PyViCareDeviceConfig
from PyViCare.PyViCareUtils import (
    PyViCareInvalidDataError,
    PyViCareNotSupportedFeatureError,
    PyViCareRateLimitError,
)
from requests.exceptions import ConnectionError as RequestConnectionError

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)

from .entity import ViCareEntity
from .types import ViCareConfigEntry, ViCareDevice
from .utils import filter_state, get_device_serial, is_supported

_LOGGER = logging.getLogger(__name__)


class VentilationProgram(enum.StrEnum):
    """ViCare preset ventilation programs.

    As listed in https://github.com/somm15/PyViCare/blob/6c5b023ca6c8bb2d38141dd1746dc1705ec84ce8/PyViCare/PyViCareVentilationDevice.py#L37
    """

    LEVEL_ONE = "levelOne"
    LEVEL_TWO = "levelTwo"
    LEVEL_THREE = "levelThree"
    LEVEL_FOUR = "levelFour"


class VentilationMode(enum.StrEnum):
    """ViCare ventilation modes."""

    PERMANENT = "permanent"  # on, speed controlled by program (levelOne-levelFour)
    VENTILATION = "ventilation"  # activated by schedule
    STANDBY = "standby"  # activated by schedule
    STANDARD = "standard"  # activated by schedule
    SENSOR_DRIVEN = "sensor_driven"  # activated by schedule, override by sensor
    SENSOR_OVERRIDE = "sensor_override"  # activated by sensor

    @staticmethod
    def to_vicare_mode(mode: str | None) -> str | None:
        """Return the mapped ViCare ventilation mode for the Home Assistant mode."""
        if mode:
            try:
                ventilation_mode = VentilationMode(mode)
            except ValueError:
                # ignore unsupported / unmapped modes
                return None
            return HA_TO_VICARE_MODE_VENTILATION.get(ventilation_mode) if mode else None
        return None

    @staticmethod
    def from_vicare_mode(vicare_mode: str | None) -> str | None:
        """Return the mapped Home Assistant mode for the ViCare ventilation mode."""
        for mode in VentilationMode:
            if HA_TO_VICARE_MODE_VENTILATION.get(VentilationMode(mode)) == vicare_mode:
                return mode
        return None


class VentilationQuickmode(enum.StrEnum):
    """ViCare ventilation quickmodes."""

    STANDBY = "standby"


HA_TO_VICARE_MODE_VENTILATION = {
    VentilationMode.PERMANENT: "permanent",
    VentilationMode.VENTILATION: "ventilation",
    VentilationMode.STANDBY: "standby",
    VentilationMode.STANDARD: "standard",
    VentilationMode.SENSOR_DRIVEN: "sensorDriven",
    VentilationMode.SENSOR_OVERRIDE: "sensorOverride",
}

ORDERED_NAMED_FAN_SPEEDS = [
    VentilationProgram.LEVEL_ONE,
    VentilationProgram.LEVEL_TWO,
    VentilationProgram.LEVEL_THREE,
    VentilationProgram.LEVEL_FOUR,
]


def _build_entities(
    device_list: list[ViCareDevice],
) -> list[ViCareFan]:
    """Create ViCare climate entities for a device."""
    return [
        ViCareFan(get_device_serial(device.api), device.config, device.api)
        for device in device_list
        if device.api.isVentilationDevice()
    ]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ViCareConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the ViCare fan platform."""
    async_add_entities(
        await hass.async_add_executor_job(
            _build_entities,
            config_entry.runtime_data.devices,
        )
    )


class ViCareFan(ViCareEntity, FanEntity):
    """Representation of the ViCare ventilation device."""

    _attr_speed_count = len(ORDERED_NAMED_FAN_SPEEDS)
    _attr_translation_key = "ventilation"
    _attributes: dict[str, Any] = {}

    def __init__(
        self,
        device_serial: str | None,
        device_config: PyViCareDeviceConfig,
        device: PyViCareDevice,
    ) -> None:
        """Initialize the fan entity."""
        super().__init__(
            self._attr_translation_key, device_serial, device_config, device
        )
        # init preset_mode
        supported_modes = list[str](self._api.getVentilationModes())
        self._attr_preset_modes = [
            mode
            for mode in VentilationMode
            if VentilationMode.to_vicare_mode(mode) in supported_modes
        ]
        if len(self._attr_preset_modes) > 0:
            self._attr_supported_features |= FanEntityFeature.PRESET_MODE
        # init set_speed
        supported_levels: list[str] | None = None
        with suppress(PyViCareNotSupportedFeatureError):
            supported_levels = self._api.getVentilationLevels()
        if supported_levels is not None and len(supported_levels) > 0:
            self._attr_supported_features |= FanEntityFeature.SET_SPEED

        # evaluate quickmodes
        self._attributes["vicare_quickmodes"] = quickmodes = list[str](
            device.getVentilationQuickmodes()
            if is_supported(
                "getVentilationQuickmodes",
                lambda api: api.getVentilationQuickmodes(),
                device,
            )
            else []
        )
        if VentilationQuickmode.STANDBY in quickmodes:
            self._attr_supported_features |= FanEntityFeature.TURN_OFF

    def update(self) -> None:
        """Update state of fan."""
        level: str | None = None
        try:
            with suppress(PyViCareNotSupportedFeatureError):
                self._attr_preset_mode = VentilationMode.from_vicare_mode(
                    self._api.getActiveVentilationMode()
                )

            with suppress(PyViCareNotSupportedFeatureError):
                level = filter_state(self._api.getVentilationLevel())
            if level is not None and level in ORDERED_NAMED_FAN_SPEEDS:
                self._attr_percentage = ordered_list_item_to_percentage(
                    ORDERED_NAMED_FAN_SPEEDS, VentilationProgram(level)
                )
            else:
                self._attr_percentage = 0
        except RequestConnectionError:
            _LOGGER.error("Unable to retrieve data from ViCare server")
        except ValueError:
            _LOGGER.error("Unable to decode data from ViCare server")
        except PyViCareRateLimitError as limit_exception:
            _LOGGER.error("Vicare API rate limit exceeded: %s", limit_exception)
        except PyViCareInvalidDataError as invalid_data_exception:
            _LOGGER.error("Invalid data from Vicare server: %s", invalid_data_exception)

    @property
    def is_on(self) -> bool | None:
        """Return true if the entity is on."""
        if VentilationQuickmode.STANDBY in self._attributes[
            "vicare_quickmodes"
        ] and self._api.getVentilationQuickmode(VentilationQuickmode.STANDBY):
            return False

        return self.percentage is not None and self.percentage > 0

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        self._api.activateVentilationQuickmode(str(VentilationQuickmode.STANDBY))

    @property
    def icon(self) -> str | None:
        """Return the icon to use in the frontend."""
        if VentilationQuickmode.STANDBY in self._attributes[
            "vicare_quickmodes"
        ] and self._api.getVentilationQuickmode(VentilationQuickmode.STANDBY):
            return "mdi:fan-off"
        if hasattr(self, "_attr_preset_mode"):
            if self._attr_preset_mode == VentilationMode.VENTILATION:
                return "mdi:fan-clock"
            if self._attr_preset_mode in [
                VentilationMode.SENSOR_DRIVEN,
                VentilationMode.SENSOR_OVERRIDE,
            ]:
                return "mdi:fan-auto"
            if self._attr_preset_mode == VentilationMode.PERMANENT:
                if self._attr_percentage == 0:
                    return "mdi:fan-off"
                if self._attr_percentage is not None:
                    level = 1 + ORDERED_NAMED_FAN_SPEEDS.index(
                        percentage_to_ordered_list_item(
                            ORDERED_NAMED_FAN_SPEEDS, self._attr_percentage
                        )
                    )
                    if level < 4:  # fan-speed- only supports 1-3
                        return f"mdi:fan-speed-{level}"
        return "mdi:fan"

    def set_percentage(self, percentage: int) -> None:
        """Set the speed of the fan, as a percentage."""
        if self._attr_preset_mode != str(VentilationMode.PERMANENT):
            self.set_preset_mode(VentilationMode.PERMANENT)
        elif VentilationQuickmode.STANDBY in self._attributes[
            "vicare_quickmodes"
        ] and self._api.getVentilationQuickmode(VentilationQuickmode.STANDBY):
            self._api.deactivateVentilationQuickmode(str(VentilationQuickmode.STANDBY))

        level = percentage_to_ordered_list_item(ORDERED_NAMED_FAN_SPEEDS, percentage)
        _LOGGER.debug("changing ventilation level to %s", level)
        self._api.setVentilationLevel(level)

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        target_mode = VentilationMode.to_vicare_mode(preset_mode)
        _LOGGER.debug("changing ventilation mode to %s", target_mode)
        self._api.activateVentilationMode(target_mode)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Show Device Attributes."""
        return self._attributes
