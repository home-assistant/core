"""Climate platform for Samsung IR integration."""

from dataclasses import dataclass
from typing import Any, override

from infrared_protocols.commands.samsung_ac import (
    SamsungAC0292Command,
    SamsungAC0292HvacMode,
    SamsungACFanMode,
    SamsungACSwingMode,
)

from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    ATTR_HVAC_MODE,
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.components.infrared import InfraredEmitterConsumerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import ExtraStoredData, RestoreEntity

from .const import CONF_DEVICE_TYPE, CONF_INFRARED_EMITTER_ENTITY_ID, SamsungDeviceType
from .entity import SamsungIrEntity

PARALLEL_UPDATES = 1


HA_TO_LIB_HVAC = {
    HVACMode.OFF: SamsungAC0292HvacMode.OFF,
    HVACMode.COOL: SamsungAC0292HvacMode.COOL,
    HVACMode.HEAT: SamsungAC0292HvacMode.HEAT,
    HVACMode.DRY: SamsungAC0292HvacMode.DRY,
    HVACMode.FAN_ONLY: SamsungAC0292HvacMode.FAN_ONLY,
    HVACMode.AUTO: SamsungAC0292HvacMode.AUTO,
}


HA_TO_LIB_FAN = {
    FAN_AUTO: SamsungACFanMode.AUTO,
    FAN_LOW: SamsungACFanMode.LOW,
    FAN_MEDIUM: SamsungACFanMode.MEDIUM,
    FAN_HIGH: SamsungACFanMode.HIGH,
}


@dataclass
class _SamsungAcExtraStoredData(ExtraStoredData):
    """Extra data restored alongside the entity's visible state.

    Holds the last non-OFF HVAC mode, which isn't part of the visible state (the
    entity may currently be OFF) but is needed by turn_on to know which mode to
    resume, so it can't be recovered from last_state.state alone when that state
    is OFF.
    """

    last_on_hvac_mode: str

    @override
    def as_dict(self) -> dict[str, Any]:
        """Return a dict representation for storage."""
        return {"last_on_hvac_mode": self.last_on_hvac_mode}

    @classmethod
    def from_dict(cls, restored: dict[str, Any]) -> _SamsungAcExtraStoredData | None:
        """Build from a stored dict, or None if it doesn't look valid."""
        last_on_hvac_mode = restored.get("last_on_hvac_mode")
        if not isinstance(last_on_hvac_mode, str):
            return None
        return cls(last_on_hvac_mode=last_on_hvac_mode)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Samsung IR climate from a config entry."""
    infrared_emitter_entity_id = entry.data[CONF_INFRARED_EMITTER_ENTITY_ID]
    device_type = entry.data[CONF_DEVICE_TYPE]

    if device_type == SamsungDeviceType.AC:
        async_add_entities(
            [SamsungIrClimate(entry, infrared_emitter_entity_id, device_type)]
        )


class SamsungIrClimate(
    SamsungIrEntity, InfraredEmitterConsumerEntity, ClimateEntity, RestoreEntity
):
    """Samsung IR climate entity."""

    _attr_name = None
    _attr_assumed_state = True
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_fan_modes = [FAN_AUTO, FAN_LOW, FAN_MEDIUM, FAN_HIGH]
    _attr_hvac_mode = HVACMode.OFF
    _attr_target_temperature = 24.0
    _attr_min_temp = 16.0
    _attr_max_temp = 30.0
    _attr_target_temperature_step = 1.0
    _attr_fan_mode = FAN_AUTO
    _attr_hvac_modes = [
        HVACMode.OFF,
        HVACMode.AUTO,
        HVACMode.COOL,
        HVACMode.HEAT,
        HVACMode.DRY,
        HVACMode.FAN_ONLY,
    ]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    def __init__(
        self, entry: ConfigEntry, infrared_emitter_entity_id: str, device_type: str
    ) -> None:
        """Initialize the climate entity."""
        super().__init__(entry, unique_id_suffix="climate", device_name="Samsung AC")
        self._infrared_emitter_entity_id = infrared_emitter_entity_id
        self._device_type = device_type

        self._last_on_hvac_mode = HVACMode.COOL

    @override
    async def async_added_to_hass(self) -> None:
        """Restore the assumed state, as infrared cannot read it back from the AC."""
        await super().async_added_to_hass()

        last_state = await self.async_get_last_state()
        if last_state is None or last_state.state in (
            STATE_UNAVAILABLE,
            STATE_UNKNOWN,
        ):
            return

        if last_state.state in self._attr_hvac_modes:
            self._attr_hvac_mode = HVACMode(last_state.state)
        if (fan_mode := last_state.attributes.get(ATTR_FAN_MODE)) in HA_TO_LIB_FAN:
            self._attr_fan_mode = fan_mode
        if (temperature := last_state.attributes.get(ATTR_TEMPERATURE)) is not None:
            self._attr_target_temperature = float(temperature)

        if self._attr_hvac_mode != HVACMode.OFF:
            self._last_on_hvac_mode = self._attr_hvac_mode
        elif (last_extra_data := await self.async_get_last_extra_data()) is not None:
            restored = _SamsungAcExtraStoredData.from_dict(last_extra_data.as_dict())
            if restored is not None and restored.last_on_hvac_mode in (
                mode.value for mode in self._attr_hvac_modes if mode != HVACMode.OFF
            ):
                self._last_on_hvac_mode = HVACMode(restored.last_on_hvac_mode)

    @property
    @override
    def extra_restore_state_data(self) -> ExtraStoredData:
        """Return extra data to be restored alongside the entity's state."""
        return _SamsungAcExtraStoredData(
            last_on_hvac_mode=self._last_on_hvac_mode.value
        )

    async def _async_send_command(self) -> None:
        """Generate the logical state and delegate transmission to the infrared platform."""
        hvac_mode = HA_TO_LIB_HVAC.get(self._attr_hvac_mode, SamsungAC0292HvacMode.OFF)

        if hvac_mode is SamsungAC0292HvacMode.OFF:
            command = SamsungAC0292Command(hvac_mode=hvac_mode)
        else:
            fan_mode = HA_TO_LIB_FAN.get(self._attr_fan_mode, SamsungACFanMode.AUTO)
            command = SamsungAC0292Command(
                hvac_mode=hvac_mode,
                target_temperature=int(self._attr_target_temperature),
                fan_mode=fan_mode,
                swing_mode=SamsungACSwingMode.OFF,
            )

        await self._send_command(command)

    @override
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode."""
        self._attr_hvac_mode = hvac_mode
        if hvac_mode != HVACMode.OFF:
            self._last_on_hvac_mode = hvac_mode
        # The unit always transmits a fixed fan value in auto mode, regardless of
        # what was previously selected; keep the reported state consistent with
        # what's actually being sent.
        if hvac_mode == HVACMode.AUTO:
            self._attr_fan_mode = FAN_AUTO

        await self._async_send_command()
        self.async_write_ha_state()

    @override
    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set fan mode."""
        self._attr_fan_mode = fan_mode
        await self._async_send_command()
        self.async_write_ha_state()

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set temperature."""
        if (hvac_mode := kwargs.get(ATTR_HVAC_MODE)) is not None:
            self._attr_hvac_mode = hvac_mode
            if hvac_mode != HVACMode.OFF:
                self._last_on_hvac_mode = hvac_mode
            if hvac_mode == HVACMode.AUTO:
                self._attr_fan_mode = FAN_AUTO

        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is not None:
            self._attr_target_temperature = round(temperature)

        if ATTR_HVAC_MODE in kwargs or ATTR_TEMPERATURE in kwargs:
            await self._async_send_command()
            self.async_write_ha_state()

    @override
    async def async_turn_on(self) -> None:
        """Turn the entity on."""
        await self.async_set_hvac_mode(self._last_on_hvac_mode)

    @override
    async def async_turn_off(self) -> None:
        """Turn the entity off."""
        await self.async_set_hvac_mode(HVACMode.OFF)
