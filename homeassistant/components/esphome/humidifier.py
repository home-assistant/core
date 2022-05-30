"""Support for ESPHome humidifier devices."""
from __future__ import annotations

from typing import Any

from aioesphomeapi import (
    HumidifierAction,
    HumidifierInfo,
    HumidifierMode,
    HumidifierPreset,
    HumidifierState,
)

from homeassistant.components.humidifier import HumidifierDeviceClass, HumidifierEntity
from homeassistant.components.humidifier.const import (
    CURRENT_HUMIDIFIER_DEHUMIDIFY,
    CURRENT_HUMIDIFIER_HUMIDIFY,
    CURRENT_HUMIDIFIER_IDLE,
    CURRENT_HUMIDIFIER_OFF,
    DEFAULT_MAX_HUMIDITY,
    DEFAULT_MIN_HUMIDITY,
    MODE_AWAY,
    MODE_BOOST,
    MODE_COMFORT,
    MODE_HOME,
    MODE_NORMAL,
    MODE_SLEEP,
    HumidifierEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import (
    EsphomeEntity,
    EsphomeEnumMapper,
    esphome_state_property,
    platform_async_setup_entry,
)

MODE_OFF = "off"

OPS_MODE_OFF = "off"
OPS_MODE_HUMIDIFY_DEHUMIDIFY = "humidify_dehumidify"
OPS_MODE_DEHUMIDIFY = "dehumidify"
OPS_MODE_HUMIDIFY = "humidify"
OPS_MODE_AUTO = "auto"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up ESPHome humidifier devices based on a config entry."""
    await platform_async_setup_entry(
        hass,
        entry,
        async_add_entities,
        component_key="humidifier",
        info_type=HumidifierInfo,
        entity_type=EsphomeHumidifierEntity,
        state_type=HumidifierState,
    )


_HUMIDIFIER_OPS_MODES: EsphomeEnumMapper[HumidifierMode, str] = EsphomeEnumMapper(
    {
        HumidifierMode.OFF: OPS_MODE_OFF,
        HumidifierMode.HUMIDIFY_DEHUMIDIFY: OPS_MODE_HUMIDIFY_DEHUMIDIFY,
        HumidifierMode.DEHUMIDIFY: OPS_MODE_DEHUMIDIFY,
        HumidifierMode.HUMIDIFY: OPS_MODE_HUMIDIFY,
        HumidifierMode.AUTO: OPS_MODE_AUTO,
    }
)
_HUMIDIFIER_PRESET_MODES: EsphomeEnumMapper[HumidifierPreset, str] = EsphomeEnumMapper(
    {
        HumidifierPreset.NORMAL: MODE_NORMAL,
        HumidifierPreset.AWAY: MODE_AWAY,
        HumidifierPreset.BOOST: MODE_BOOST,
        HumidifierPreset.COMFORT: MODE_COMFORT,
        HumidifierPreset.HOME: MODE_HOME,
        HumidifierPreset.SLEEP: MODE_SLEEP,
    }
)
_HUMIDIFIER_ACTIONS: EsphomeEnumMapper[HumidifierAction, str] = EsphomeEnumMapper(
    {
        HumidifierAction.OFF: CURRENT_HUMIDIFIER_OFF,
        HumidifierAction.DEHUMIDIFYING: CURRENT_HUMIDIFIER_DEHUMIDIFY,
        HumidifierAction.HUMIDIFYING: CURRENT_HUMIDIFIER_HUMIDIFY,
        HumidifierAction.IDLE: CURRENT_HUMIDIFIER_IDLE,
    }
)

# https://github.com/PyCQA/pylint/issues/3150 for all @esphome_state_property
# pylint: disable=invalid-overridden-method


class EsphomeHumidifierEntity(
    EsphomeEntity[HumidifierInfo, HumidifierState], HumidifierEntity
):
    """A humidifier implementation for ESPHome."""

    @property
    def available_modes(self) -> list[str]:
        """Return the list of available preset modes."""
        return [
            _HUMIDIFIER_PRESET_MODES.from_esphome(preset)
            for preset in self._static_info.supported_presets
        ]

    @property
    def device_class(self) -> str:
        """Return the device class type."""
        if HumidifierMode.HUMIDIFY in self._static_info.supported_modes:
            return HumidifierDeviceClass.HUMIDIFIER
        return HumidifierDeviceClass.DEHUMIDIFIER

    @property
    def is_on(self) -> bool:
        """Return True if the humidifier is on."""
        return self.ops_mode() != OPS_MODE_OFF

    @property
    def max_humidity(self) -> int:
        """Return the maximum humidity."""
        return DEFAULT_MAX_HUMIDITY

    @property
    def min_humidity(self) -> int:
        """Return the minimum humidity."""
        return DEFAULT_MIN_HUMIDITY

    @esphome_state_property
    def mode(self) -> str | None:
        """Return the current preset mode, e.g. none, home, away, etc."""
        return _HUMIDIFIER_PRESET_MODES.from_esphome(self._state.preset)

    def ops_mode(self) -> str | None:
        """Return the current operations mode, e.g. off, humidify, dehumidify, etc."""
        return _HUMIDIFIER_OPS_MODES.from_esphome(self._state.mode)

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return HumidifierEntityFeature.MODES

    @esphome_state_property
    def target_humidity(self) -> int | None:
        """Return the humidity we try to reach."""
        # HA has no support for two-point target humidity, make the target an
        # average between the low and high
        if self._static_info.supports_two_point_target_humidity:
            return int(
                (self._state.target_humidity_low + self._state.target_humidity_high) / 2
            )
        return int(self._state.target_humidity)

    async def async_set_humidity(self, humidity: int) -> None:
        """Set new target humidity (and operation mode if set)."""
        data: dict[str, Any] = {"key": self._static_info.key}
        # HA has no support yet for two-point target humidity, make it a 10% range
        if self._static_info.supports_two_point_target_humidity:
            data["target_humidity_low"] = max(humidity - 5, 0)
            data["target_humidity_high"] = min(humidity + 5, 100)
        else:
            data["target_humidity"] = humidity
        await self._client.humidifier_command(**data)

    async def async_set_mode(self, mode: str) -> None:
        """Set new target preset mode (eco, home, etc.)."""
        await self._client.humidifier_command(
            key=self._static_info.key, preset=_HUMIDIFIER_PRESET_MODES.from_hass(mode)
        )

    async def async_set_ops_mode(self, mode: str) -> None:
        """Set new target operation mode (off, humidify, dehumidify, auto, etc.)."""
        await self._client.humidifier_command(
            key=self._static_info.key, mode=_HUMIDIFIER_OPS_MODES.from_hass(mode)
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Set humidifier to on mode."""
        if self._static_info.supports_two_point_target_humidity:
            await self.async_set_ops_mode(OPS_MODE_HUMIDIFY_DEHUMIDIFY)
        elif HumidifierMode.HUMIDIFY in self._static_info.supported_modes:
            await self.async_set_ops_mode(OPS_MODE_HUMIDIFY)
        else:
            await self.async_set_ops_mode(OPS_MODE_DEHUMIDIFY)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Set humidifier to off operation mode."""
        await self.async_set_ops_mode(OPS_MODE_OFF)

    @esphome_state_property
    def humidifier_action(self) -> str | None:
        """Return current action."""
        # HA has no support feature field for humidifier_action
        if not self._static_info.supports_action:
            return None
        return _HUMIDIFIER_ACTIONS.from_esphome(self._state.action)
