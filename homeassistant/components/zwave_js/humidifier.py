"""Representation of Z-Wave thermostats."""
from __future__ import annotations

from typing import Any, cast

from zwave_js_server.client import Client as ZwaveClient
from zwave_js_server.const import CommandClass
from zwave_js_server.const.command_class.humidity_control import (
    HUMIDITY_CONTROL_MODE_PROPERTY,
    HUMIDITY_CONTROL_MODE_SETPOINT_MAP,
    HUMIDITY_CONTROL_OPERATING_STATE_PROPERTY,
    HUMIDITY_CONTROL_SETPOINT_PROPERTY,
    HumidityControlMode,
    HumidityControlSetpointType,
)
from zwave_js_server.model.value import Value as ZwaveValue

from homeassistant.components.humidifier import HumidifierDeviceClass, HumidifierEntity
from homeassistant.components.humidifier.const import (
    DEFAULT_MAX_HUMIDITY,
    DEFAULT_MIN_HUMIDITY,
    DOMAIN as HUMIDIFIER_DOMAIN,
    SUPPORT_MODES,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_CLIENT, DOMAIN
from .discovery import ZwaveDiscoveryInfo
from .entity import ZWaveBaseEntity

ATTR_OPERATING_STATE = "operating_state"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Z-Wave humidifier from config entry."""
    client: ZwaveClient = hass.data[DOMAIN][config_entry.entry_id][DATA_CLIENT]

    @callback
    def async_add_humidifier(info: ZwaveDiscoveryInfo) -> None:
        """Add Z-Wave Humidifier."""
        entities: list[ZWaveBaseEntity] = []

        entities.append(ZWaveHumidifier(config_entry, client, info))

        async_add_entities(entities)

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            f"{DOMAIN}_{config_entry.entry_id}_add_{HUMIDIFIER_DOMAIN}",
            async_add_humidifier,
        )
    )


class ZWaveHumidifier(ZWaveBaseEntity, HumidifierEntity):
    """Representation of a Z-Wave Humidifier."""

    def __init__(
        self,
        config_entry: ConfigEntry,
        client: ZwaveClient,
        info: ZwaveDiscoveryInfo,
    ) -> None:
        """Initialize thermostat."""
        super().__init__(config_entry, client, info)

        self._attr_supported_features = SUPPORT_MODES
        self._attr_available_modes = []

        self._current_mode = self.get_zwave_value(
            HUMIDITY_CONTROL_MODE_PROPERTY,
            command_class=CommandClass.HUMIDITY_CONTROL_MODE,
        )

        if self._current_mode:
            if (
                str(HumidityControlMode.HUMIDIFY.value)
                in self._current_mode.metadata.states
            ):
                self._attr_device_class = HumidifierDeviceClass.HUMIDIFIER
            else:
                self._attr_device_class = HumidifierDeviceClass.DEHUMIDIFIER

            for mode in self._current_mode.metadata.states:
                self._attr_available_modes.append(
                    self._current_mode.metadata.states[mode]
                )

        self._operating_state = self.get_zwave_value(
            HUMIDITY_CONTROL_OPERATING_STATE_PROPERTY,
            command_class=CommandClass.HUMIDITY_CONTROL_OPERATING_STATE,
        )

        self._setpoint_values: dict[HumidityControlSetpointType, ZwaveValue] = {}

        for setpoint_type in HumidityControlSetpointType:
            setpoint_value = self.get_zwave_value(
                HUMIDITY_CONTROL_SETPOINT_PROPERTY,
                command_class=CommandClass.HUMIDITY_CONTROL_SETPOINT,
                value_property_key=setpoint_type,
                add_to_watched_value_ids=True,
            )
            if setpoint_value:
                self._setpoint_values[setpoint_type] = setpoint_value

    def _setpoint_type_for_current_mode(self) -> HumidityControlSetpointType:
        if self._current_mode:
            return HUMIDITY_CONTROL_MODE_SETPOINT_MAP.get(
                int(self._current_mode.value), []
            )
        return None

    @property
    def _setpoint_value(self) -> ZwaveValue | None:
        """Optionally return a ZwaveValue for a setpoint."""

        setpoint_types = self._setpoint_type_for_current_mode()
        if len(setpoint_types) == 0:
            return None

        setpoint_type = setpoint_types[0]
        if (
            setpoint_type is None
            or setpoint_type not in self._setpoint_values
            or (val := self._setpoint_values[setpoint_type]) is None
        ):
            raise ValueError("Value requested is not available")

        return val

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Set new target humidity."""
        if self._current_mode:
            if (
                str(HumidityControlMode.AUTO.value)
                in self._current_mode.metadata.states
            ):
                new_mode = HumidityControlMode.AUTO
            elif (
                str(HumidityControlMode.HUMIDIFY.value)
                in self._current_mode.metadata.states
            ):
                new_mode = HumidityControlMode.HUMIDIFY
            else:
                new_mode = HumidityControlMode.DEHUMIDIFY
            await self.info.node.async_set_value(self._current_mode, new_mode)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Set new target humidity."""
        if self._current_mode:
            await self.info.node.async_set_value(
                self._current_mode, HumidityControlMode.OFF
            )

    @property
    def is_on(self) -> bool | None:
        """Return True if entity is on."""
        if self._current_mode is None:
            return None
        return cast(bool, int(self._current_mode.value) != HumidityControlMode.OFF)

    @property
    def target_humidity(self) -> int | None:
        """Return the humidity we try to reach."""
        if not self.is_on or self._setpoint_value is None:
            return None
        return int(self._setpoint_value.value)

    @property
    def mode(self) -> str | None:
        """Return the current humidity control mode."""
        if self._current_mode:
            return cast(
                str, self._current_mode.metadata.states[str(self._current_mode.value)]
            )
        return None

    async def async_set_mode(self, mode: str) -> None:
        """Set new mode."""

        if self._current_mode is None:
            return None

        try:
            new_state = int(
                next(
                    state
                    for state, label in self._current_mode.metadata.states.items()
                    if label == mode
                )
            )
        except StopIteration:
            raise ValueError(f"Received an invalid mode: {mode}") from None

        await self.info.node.async_set_value(self._current_mode, new_state)

    async def async_set_humidity(self, humidity: int) -> None:
        """Set new target humidity."""
        await self.info.node.async_set_value(self._setpoint_value, humidity)

    @property
    def min_humidity(self) -> int:
        """Return the minimum humidity."""
        min_value = DEFAULT_MIN_HUMIDITY
        try:
            if self._setpoint_value and self._setpoint_value.metadata.min:
                min_value = self._setpoint_value.metadata.min
        # In case of any error, we fallback to the default
        except (IndexError, ValueError, TypeError):
            pass

        return min_value

    @property
    def max_humidity(self) -> int:
        """Return the maximum humidity."""
        max_value = DEFAULT_MAX_HUMIDITY
        try:
            if self._setpoint_value and self._setpoint_value.metadata.max:
                max_value = self._setpoint_value.metadata.max
        # In case of any error, we fallback to the default
        except (IndexError, ValueError, TypeError):
            pass

        return max_value

    @property
    def operating_state(self) -> str | None:
        """Return the current humidity control operating state."""
        if self._operating_state:
            return cast(
                str,
                self._operating_state.metadata.states[str(self._operating_state.value)],
            )
        return None

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Return the optional state attributes."""
        attrs = {}

        if state := self.operating_state:
            attrs[ATTR_OPERATING_STATE] = state

        return attrs
