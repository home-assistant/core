"""Light platform for Honeywell String Lights."""

from typing import Any, override

from rf_protocols.codes.honeywell.string_lights import CODES

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.components.radio_frequency import (
    RadioFrequencyTransmitterConsumerEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import CONF_TRANSMITTER
from .entity import HoneywellStringLightsEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Honeywell String Lights light platform."""
    async_add_entities([HoneywellStringLight(config_entry)])


class HoneywellStringLight(
    HoneywellStringLightsEntity,
    RadioFrequencyTransmitterConsumerEntity,
    LightEntity,
    RestoreEntity,
):
    """Representation of a Honeywell String Lights set controlled via RF."""

    _attr_assumed_state = True
    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}
    _attr_name = None

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the entity."""
        super().__init__(entry)
        self._rf_transmitter_entity_id = entry.data[CONF_TRANSMITTER]

    @override
    async def async_added_to_hass(self) -> None:
        """Restore last known state."""
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None:
            self._attr_is_on = last_state.state == STATE_ON

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        await self._async_send_rf_command("turn_on")
        self._attr_is_on = True
        self.async_write_ha_state()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        await self._async_send_rf_command("turn_off")
        self._attr_is_on = False
        self.async_write_ha_state()

    async def _async_send_rf_command(self, name: str) -> None:
        """Load the named command and send it via the configured transmitter."""
        command = await CODES.async_load_command(name)
        await self._send_command(command)
