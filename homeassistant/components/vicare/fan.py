"""Viessmann ViCare ventilation device."""

from __future__ import annotations

from contextlib import suppress
import enum
import logging

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
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)

from .entity import ViCareEntity
from .types import ViCareConfigEntry, ViCareDevice
from .utils import get_device_serial

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


HA_TO_VICARE_MODE_VENTILATION = {
    VentilationMode.PERMANENT: "permanent",
    VentilationMode.VENTILATION: "ventilation",
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
        if isinstance(device.api, PyViCareVentilationDevice)
    ]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ViCareConfigEntry,
    async_add_entities: AddEntitiesCallback,
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
    _attr_supported_features = FanEntityFeature.SET_SPEED
    _attr_translation_key = "ventilation"

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
        # init presets
        supported_modes = list[str](self._api.getAvailableModes())
        self._attr_preset_modes = [
            mode
            for mode in VentilationMode
            if VentilationMode.to_vicare_mode(mode) in supported_modes
        ]
        if len(self._attr_preset_modes) > 0:
            self._attr_supported_features |= FanEntityFeature.PRESET_MODE

    def update(self) -> None:
        """Update state of fan."""
        try:
            with suppress(PyViCareNotSupportedFeatureError):
                self._attr_preset_mode = VentilationMode.from_vicare_mode(
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

    @property
    def is_on(self) -> bool | None:
        """Return true if the entity is on."""
        # Viessmann ventilation unit cannot be turned off
        return True

    @property
    def icon(self) -> str | None:
        """Return the icon to use in the frontend."""
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

        level = percentage_to_ordered_list_item(ORDERED_NAMED_FAN_SPEEDS, percentage)
        _LOGGER.debug("changing ventilation level to %s", level)
        self._api.setPermanentLevel(level)

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        target_mode = VentilationMode.to_vicare_mode(preset_mode)
        _LOGGER.debug("changing ventilation mode to %s", target_mode)
        self._api.setActiveMode(target_mode)
