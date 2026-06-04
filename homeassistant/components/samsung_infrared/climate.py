"""Climate platform for Samsung IR integration."""

from typing import Any

from infrared_protocols.codes.samsung.ac import SamsungACStateBuilder

from homeassistant.components.climate import (
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
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_DEVICE_TYPE, CONF_INFRARED_EMITTER_ENTITY_ID, SamsungDeviceType
from .entity import SamsungIrEntity

PARALLEL_UPDATES = 0

# Map Home Assistant HVAC modes to library string representations
HA_TO_LIB_HVAC = {
    HVACMode.OFF: "off",
    HVACMode.COOL: "cool",
    HVACMode.HEAT: "heat",
    HVACMode.DRY: "dry",
    HVACMode.FAN_ONLY: "fan_only",
}

# Map Home Assistant fan modes to library string representations
HA_TO_LIB_FAN = {
    FAN_AUTO: "auto",
    FAN_LOW: "low",
    FAN_MEDIUM: "medium",
    FAN_HIGH: "high",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Samsung IR climate from a config entry."""
    infrared_emitter_entity_id = entry.data[CONF_INFRARED_EMITTER_ENTITY_ID]
    device_type = entry.data[CONF_DEVICE_TYPE]

    if device_type == SamsungDeviceType.AC:
        async_add_entities([SamsungIrClimate(entry, infrared_emitter_entity_id)])


class SamsungIrClimate(SamsungIrEntity, InfraredEmitterConsumerEntity, ClimateEntity):
    """Samsung IR climate entity."""

    _attr_name = None
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [
        HVACMode.OFF,
        HVACMode.COOL,
        HVACMode.HEAT,
        HVACMode.DRY,
        HVACMode.FAN_ONLY,
    ]
    _attr_fan_modes = [FAN_AUTO, FAN_LOW, FAN_MEDIUM, FAN_HIGH]
    _attr_hvac_mode = HVACMode.OFF
    _attr_target_temperature = 24.0
    _attr_fan_mode = FAN_AUTO
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    def __init__(self, entry: ConfigEntry, infrared_emitter_entity_id: str) -> None:
        """Initialize the climate entity."""
        super().__init__(entry, unique_id_suffix="climate", device_name="Samsung AC")
        self._infrared_emitter_entity_id = infrared_emitter_entity_id

    async def _async_send_command(self) -> None:
        """Generate the logical state and delegate transmission to the infrared platform."""
        # Build the logical state using the external library class
        builder = SamsungACStateBuilder(
            hvac_mode=HA_TO_LIB_HVAC.get(self._attr_hvac_mode, "off"),
            target_temperature=int(self._attr_target_temperature),
            fan_mode=HA_TO_LIB_FAN.get(self._attr_fan_mode, "auto"),
        )
        # to_command() returns the concrete sub-classed command object
        await self._send_command(builder.to_command())

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode."""
        self._attr_hvac_mode = hvac_mode
        await self._async_send_command()
        self.async_write_ha_state()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set fan mode."""
        self._attr_fan_mode = fan_mode
        await self._async_send_command()
        self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is not None:
            self._attr_target_temperature = temperature
            await self._async_send_command()
            self.async_write_ha_state()
