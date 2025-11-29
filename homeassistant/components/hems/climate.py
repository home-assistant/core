"""Climate platform for the HEMS integration."""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any

from pyhems import Property

from homeassistant.components.climate import (
    ATTR_TEMPERATURE,
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    SWING_BOTH,
    SWING_HORIZONTAL,
    SWING_OFF,
    SWING_VERTICAL,
    ClimateEntity,
    ClimateEntityDescription,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import PRECISION_WHOLE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import HemsCoordinator
from .definitions import NumericDecoderSpec
from .entity import HemsEntity
from .types import HemsConfigEntry, HemsNodeState

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

# Climate class codes (local to this platform)
CLASS_CODE_HOME_AIR_CONDITIONER = 0x0130
CLIMATE_CLASS_CODES: frozenset[int] = frozenset({CLASS_CODE_HOME_AIR_CONDITIONER})

# Climate-specific EPCs (local to this platform)
EPC_OPERATION_STATUS = 0x80
EPC_FAN_SPEED = 0xA0
EPC_SWING_AIR_FLOW = 0xA3
EPC_OPERATION_MODE = 0xB0
EPC_TARGET_TEMPERATURE = 0xB3
EPC_ROOM_TEMPERATURE = 0xBB

# EPCs we want to obtain (via 0x63 or 0x62) for climate devices.
CLIMATE_MONITORED_EPCS: dict[int, frozenset[int]] = {
    CLASS_CODE_HOME_AIR_CONDITIONER: frozenset(
        {
            EPC_OPERATION_STATUS,
            EPC_OPERATION_MODE,
            EPC_TARGET_TEMPERATURE,
            EPC_ROOM_TEMPERATURE,
            EPC_FAN_SPEED,
            EPC_SWING_AIR_FLOW,
        }
    ),
}

# Minimal EPCs needed to construct the climate entity (gate).
_CLIMATE_REQUIRED_EPCS: dict[int, frozenset[int]] = {
    CLASS_CODE_HOME_AIR_CONDITIONER: frozenset(
        {
            EPC_OPERATION_STATUS,
            EPC_OPERATION_MODE,
            EPC_TARGET_TEMPERATURE,
            EPC_ROOM_TEMPERATURE,
        }
    ),
}

_SUPPORTED_HVAC_MODES: list[HVACMode] = [
    HVACMode.OFF,
    HVACMode.AUTO,
    HVACMode.COOL,
    HVACMode.HEAT,
    HVACMode.DRY,
    HVACMode.FAN_ONLY,
]

_HA_TO_ECHONET_MODE: dict[HVACMode, int] = {
    HVACMode.AUTO: 0x41,
    HVACMode.COOL: 0x42,
    HVACMode.HEAT: 0x43,
    HVACMode.DRY: 0x44,
    HVACMode.FAN_ONLY: 0x45,
}
_ECHONET_TO_HA_MODE = {v: k for k, v in _HA_TO_ECHONET_MODE.items()}

_ECHONET_TO_HA_ACTION: dict[int, HVACAction] = {
    0x42: HVACAction.COOLING,
    0x43: HVACAction.HEATING,
    0x44: HVACAction.DRYING,
    0x45: HVACAction.FAN,
}

# Fan speed mapping (0xA0 Air flow rate setting)
_HA_TO_ECHONET_FAN: dict[str, int] = {
    FAN_AUTO: 0x41,
    FAN_LOW: 0x31,  # Level 1
    "Level 2": 0x32,  # Level 2
    "Level 3": 0x33,  # Level 3
    "Level 4": 0x34,  # Level 4
    "Level 5": 0x35,  # Level 5
    "Level 6": 0x36,  # Level 6
    "Level 7": 0x37,  # Level 7
    FAN_HIGH: 0x38,  # Level 8
}
_ECHONET_TO_HA_FAN = {v: k for k, v in _HA_TO_ECHONET_FAN.items()}

# Swing mode mapping (0xA3 Swing direction setting)
_HA_TO_ECHONET_SWING: dict[str, int] = {
    SWING_OFF: 0x31,
    SWING_VERTICAL: 0x41,
    SWING_HORIZONTAL: 0x42,
    SWING_BOTH: 0x43,
}
_ECHONET_TO_HA_SWING = {v: k for k, v in _HA_TO_ECHONET_SWING.items()}


# Climate entity description for home air conditioner
_CLIMATE_DESCRIPTION = ClimateEntityDescription(
    key="climate",
    translation_key="home_air_conditioner",
)


def _should_create_climate(node: HemsNodeState) -> bool:
    """Check if climate entity should be created for this node.

    Climate requires a minimal set of EPCs at discovery.
    """
    required = _CLIMATE_REQUIRED_EPCS.get(node.eoj >> 8, frozenset())
    return required.issubset(node.get_epcs)


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: HemsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up HEMS climate entities from a config entry."""
    assert entry.runtime_data is not None
    coordinator = entry.runtime_data.coordinator

    @callback
    def _async_add_entities_for_devices(device_keys: set[str]) -> None:
        """Create climate entities for the given device keys."""
        new_entities: list[HemsClimate] = []
        for device_key in device_keys:
            node = coordinator.data.get(device_key)
            if not node:
                continue

            class_code = node.eoj >> 8
            if class_code not in CLIMATE_CLASS_CODES:
                continue

            if _should_create_climate(node):
                new_entities.append(HemsClimate(coordinator, node))
        if new_entities:
            async_add_entities(new_entities)

    @callback
    def _async_process_coordinator_update() -> None:
        """Handle coordinator update - process only new devices."""
        if coordinator.new_device_keys:
            _async_add_entities_for_devices(coordinator.new_device_keys)

    entry.async_on_unload(
        coordinator.async_add_listener(_async_process_coordinator_update)
    )
    # Initial setup: process all existing devices
    _async_add_entities_for_devices(set(coordinator.data.keys()))


class HemsClimate(HemsEntity, ClimateEntity):
    """Representation of an ECHONET Lite HVAC device.

    This implementation uses a property caching pattern via async_update() to
    efficiently manage the many climate entity properties. Instead of calling
    _get_property() separately for each property getter (hvac_mode, target_temperature,
    fan_mode, etc.).

    This approach provides several benefits:
    - Reduces multiple property lookups to a single batch operation per update cycle
    - Ensures consistency across all properties within a single update cycle
    - Aligns with Home Assistant's recommended entity update patterns
    - Simplifies property getters (no complex logic, just return cached values)
    """

    entity_description: ClimateEntityDescription
    _attr_has_entity_name = True
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_precision = PRECISION_WHOLE
    _attr_hvac_modes = _SUPPORTED_HVAC_MODES
    _attr_fan_modes = list(_HA_TO_ECHONET_FAN.keys())
    _attr_min_temp = 0.0
    _attr_max_temp = 50.0

    def __init__(
        self,
        coordinator: HemsCoordinator,
        node: HemsNodeState,
    ) -> None:
        """Initialize a HEMS climate entity."""
        super().__init__(coordinator, node)
        self.entity_description = _CLIMATE_DESCRIPTION
        self._attr_unique_id = f"{node.device_key}-{_CLIMATE_DESCRIPTION.key}"
        self._attr_translation_key = _CLIMATE_DESCRIPTION.translation_key
        features = ClimateEntityFeature(0)
        swing_modes: list[str] | None = None
        if EPC_TARGET_TEMPERATURE in node.get_epcs:
            features |= ClimateEntityFeature.TARGET_TEMPERATURE
        if EPC_FAN_SPEED in node.get_epcs:
            features |= ClimateEntityFeature.FAN_MODE
        if EPC_SWING_AIR_FLOW in node.get_epcs:
            features |= ClimateEntityFeature.SWING_MODE
            swing_modes = list(_HA_TO_ECHONET_SWING.keys())
        if EPC_OPERATION_STATUS in node.set_epcs:
            features |= ClimateEntityFeature.TURN_ON
            features |= ClimateEntityFeature.TURN_OFF
        self._attr_supported_features = features
        self._attr_swing_modes = swing_modes

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return the current HVAC mode."""
        if self._get_value(EPC_OPERATION_STATUS, lambda edt: edt == b"\x30"):
            return self._get_value(
                EPC_OPERATION_MODE, lambda edt: _ECHONET_TO_HA_MODE.get(edt[0])
            )
        return HVACMode.OFF

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the current HVAC action."""
        if self._get_value(EPC_OPERATION_STATUS, lambda edt: edt == b"\x30"):
            return self._get_value(
                EPC_OPERATION_MODE, lambda edt: _ECHONET_TO_HA_ACTION.get(edt[0])
            )
        return HVACAction.OFF

    @property
    def fan_mode(self) -> str | None:
        """Return the current fan mode."""
        return self._get_value(
            EPC_FAN_SPEED, lambda edt: _ECHONET_TO_HA_FAN.get(edt[0])
        )

    @property
    def swing_mode(self) -> str | None:
        """Return the current swing mode based on vertical/horizontal settings."""
        return self._get_value(
            EPC_SWING_AIR_FLOW, lambda edt: _ECHONET_TO_HA_SWING.get(edt[0])
        )

    @property
    def current_temperature(self) -> float | None:
        """Return the measured indoor temperature."""
        return self._get_value(EPC_ROOM_TEMPERATURE, _SIGNED_BYTE_TEMPERATURE_DECODER)

    @property
    def target_temperature(self) -> float | None:
        """Return the currently configured setpoint."""
        return self._get_value(EPC_TARGET_TEMPERATURE, _decode_unsigned_temperature)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the requested HVAC mode."""
        _LOGGER.debug(
            "async_set_hvac_mode: Requested mode=%s, current mode=%s",
            hvac_mode,
            self.hvac_mode,
        )
        if hvac_mode == HVACMode.OFF:
            await self.async_turn_off()
            return

        if EPC_OPERATION_MODE not in self._node.set_epcs:
            raise HomeAssistantError("Operation mode is not writable")
        if EPC_OPERATION_STATUS not in self._node.set_epcs:
            raise HomeAssistantError("Operation status is not writable")
        echonet_mode = _HA_TO_ECHONET_MODE.get(hvac_mode)
        if echonet_mode is None:
            raise HomeAssistantError(f"Unsupported HVAC mode: {hvac_mode}")
        await self._async_send_properties(
            [
                Property(epc=EPC_OPERATION_MODE, edt=bytes([echonet_mode])),
                Property(epc=EPC_OPERATION_STATUS, edt=b"\x30"),
            ]
        )

    async def async_turn_on(self) -> None:
        """Turn on the climate device."""
        if EPC_OPERATION_STATUS not in self._node.set_epcs:
            raise HomeAssistantError("Operation status is not writable")
        await self._async_send_property(EPC_OPERATION_STATUS, b"\x30")

    async def async_turn_off(self) -> None:
        """Turn off the climate device."""
        if EPC_OPERATION_STATUS not in self._node.set_epcs:
            raise HomeAssistantError("Operation status is not writable")
        await self._async_send_property(EPC_OPERATION_STATUS, b"\x31")

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the target temperature for the current mode."""
        if ATTR_TEMPERATURE not in kwargs or kwargs[ATTR_TEMPERATURE] is None:
            raise HomeAssistantError("Target temperature is required")
        temperature = float(kwargs[ATTR_TEMPERATURE])
        if EPC_TARGET_TEMPERATURE not in self._node.set_epcs:
            raise HomeAssistantError(
                f"Temperature setpoint (0x{EPC_TARGET_TEMPERATURE:02X}) is not writable"
            )
        await self._async_send_property(
            EPC_TARGET_TEMPERATURE, _encode_temperature(temperature)
        )

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set the fan mode."""
        if EPC_FAN_SPEED not in self._node.set_epcs:
            raise HomeAssistantError("Fan mode is not writable by this device")
        fan_value = _HA_TO_ECHONET_FAN.get(fan_mode)
        if fan_value is None:
            raise HomeAssistantError(f"Unsupported fan mode: {fan_mode}")
        await self._async_send_property(EPC_FAN_SPEED, bytes([fan_value]))

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set the swing mode."""
        if EPC_SWING_AIR_FLOW not in self._node.set_epcs:
            raise HomeAssistantError("Swing mode is not writable by this device")
        swing_value = _HA_TO_ECHONET_SWING.get(swing_mode)
        if swing_value is None:
            raise HomeAssistantError(f"Unsupported swing mode: {swing_mode}")
        await self._async_send_property(EPC_SWING_AIR_FLOW, bytes([swing_value]))

    def _get_value(self, epc: int, converter: Callable[[bytes], Any]) -> Any:
        """Helper to get and decode a property value from the node."""
        if edt := self._node.properties.get(epc):
            return converter(edt)
        return None


def _decode_unsigned_temperature(edt: bytes) -> float | None:
    if len(edt) != 1:
        return None
    value = edt[0]
    return None if value == 0xFD else float(value)


# Decoder for signed byte temperature (ECHONET Lite specification)
# Handles special values: 0x7E (immeasurable), 0x7F (overflow), 0x80 (underflow)
_SIGNED_BYTE_TEMPERATURE_DECODER = NumericDecoderSpec(
    type="temperature", byte_count=1, scale=1.0
).create_decoder()


def _encode_temperature(value: float) -> bytes:
    bounded = max(0, min(50, int(round(value))))
    return bytes([bounded])


__all__ = ["HemsClimate"]
