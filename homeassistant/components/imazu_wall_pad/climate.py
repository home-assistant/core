"""Climate platform for Imazu Wall Pad integration."""
from typing import Any

from wp_imazu.packet import ThermostatPacket

from homeassistant import config_entries
from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, Platform, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ImazuGateway
from .const import DOMAIN
from .gateway import EntityData
from .wall_pad import WallPadDevice

SCAN_THERMOSTAT_PACKETS = ["01180146100000"]

MODE_OFF = "Off"
MODE_HEAT = "Heat"
MODE_AWAY = "Away"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize Imazu Wall Pad config entry."""
    gateway: ImazuGateway = hass.data[DOMAIN].get(config_entry.entry_id)

    @callback
    def async_add_entity(data: EntityData):
        if data.device:
            return

        if isinstance(data.packet, ThermostatPacket):
            data.device = WPClimate(gateway.client, Platform.CLIMATE, data.packet)

        if data.device:
            async_add_entities([data.device])

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass, gateway.entity_add_signal(Platform.CLIMATE), async_add_entity
        )
    )

    if not gateway.add_platform_entities(Platform.CLIMATE):
        for packet in SCAN_THERMOSTAT_PACKETS:
            await gateway.client.async_send(bytes.fromhex(packet))


class WPClimate(WallPadDevice[ThermostatPacket], ClimateEntity):
    """Representation of a Wall Pad climate."""

    _attr_max_temp = 35
    _attr_min_temp = 5
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
    _attr_preset_modes = [MODE_OFF, MODE_HEAT, MODE_AWAY]
    _attr_target_temperature_high = 35
    _attr_target_temperature_low = 5
    _attr_target_temperature_step = 1
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
    )

    @property
    def current_temperature(self) -> float:
        """Return the current temperature."""
        return self.packet.state["temp"]

    @property
    def target_temperature(self) -> float:
        """Return the temperature we try to reach."""
        return self.packet.state["target"]

    @property
    def hvac_action(self) -> HVACAction:
        """Return the current running hvac operation if supported."""
        if self.hvac_mode == HVACMode.HEAT:
            return HVACAction.HEATING
        return HVACAction.OFF

    @property
    def hvac_mode(self) -> HVACMode:
        """Return hvac operation ie. heat, cool mode."""
        if not self.available:
            return HVACMode.OFF

        if self.packet.state["mode"] == ThermostatPacket.Mode.OFF:
            return HVACMode.OFF
        return HVACMode.HEAT

    @property
    def preset_mode(self) -> str:
        """Return the current preset mode."""
        if not self.available:
            return MODE_OFF

        mode: ThermostatPacket.Mode = self.packet.state["mode"]
        if mode == ThermostatPacket.Mode.HEAT:
            return MODE_HEAT
        if mode == ThermostatPacket.Mode.AWAY:
            return MODE_AWAY
        return MODE_OFF

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        if hvac_mode == HVACMode.HEAT:
            await self.async_set_preset_mode(MODE_HEAT)
        else:
            await self.async_set_preset_mode(MODE_OFF)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if (target := int(kwargs[ATTR_TEMPERATURE])) is None:
            return
        make_packet = self.packet.make_change_target_temp(target)
        await super().async_send_packet(make_packet)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the climate."""
        if preset_mode == MODE_HEAT:
            make_packet = self.packet.make_change_mode(ThermostatPacket.Mode.HEAT)
        elif preset_mode == MODE_AWAY:
            make_packet = self.packet.make_change_mode(ThermostatPacket.Mode.AWAY)
        else:
            make_packet = self.packet.make_change_mode(ThermostatPacket.Mode.OFF)
        await super().async_send_packet(make_packet)

    async def async_turn_on(self) -> None:
        """Turn on climate."""
        await self.async_set_hvac_mode(HVACMode.HEAT)

    async def async_turn_off(self) -> None:
        """Turn off climate."""
        await self.async_set_hvac_mode(HVACMode.OFF)
