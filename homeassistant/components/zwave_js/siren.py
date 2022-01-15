"""Support for Z-Wave controls using the siren platform."""
from __future__ import annotations

from typing import Any

from zwave_js_server.client import Client as ZwaveClient
from zwave_js_server.const.command_class.sound_switch import ToneID

from homeassistant.components.siren import DOMAIN as SIREN_DOMAIN, SirenEntity
from homeassistant.components.siren.const import (
    ATTR_TONE,
    ATTR_VOLUME_LEVEL,
    SUPPORT_TONES,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_SET,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_CLIENT, DOMAIN
from .discovery import ZwaveDiscoveryInfo
from .entity import ZWaveBaseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Z-Wave Siren entity from Config Entry."""
    client: ZwaveClient = hass.data[DOMAIN][config_entry.entry_id][DATA_CLIENT]

    @callback
    def async_add_siren(info: ZwaveDiscoveryInfo) -> None:
        """Add Z-Wave siren entity."""
        entities: list[ZWaveBaseEntity] = []
        entities.append(ZwaveSirenEntity(config_entry, client, info))
        async_add_entities(entities)

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            f"{DOMAIN}_{config_entry.entry_id}_add_{SIREN_DOMAIN}",
            async_add_siren,
        )
    )


class ZwaveSirenEntity(ZWaveBaseEntity, SirenEntity):
    """Representation of a Z-Wave siren entity."""

    def __init__(
        self, config_entry: ConfigEntry, client: ZwaveClient, info: ZwaveDiscoveryInfo
    ) -> None:
        """Initialize a ZwaveSirenEntity entity."""
        super().__init__(config_entry, client, info)
        # Entity class attributes
        self._attr_available_tones = {
            int(id): val for id, val in self.info.primary_value.metadata.states.items()
        }
        self._attr_supported_features = (
            SUPPORT_TURN_ON | SUPPORT_TURN_OFF | SUPPORT_VOLUME_SET
        )
        if self._attr_available_tones:
            self._attr_supported_features |= SUPPORT_TONES

    @property
    def is_on(self) -> bool:
        """Return whether device is on."""
        return bool(self.info.primary_value.value)

    async def async_set_value(
        self, new_value: int, options: dict[str, Any] | None = None
    ) -> None:
        """Set a value on a siren node."""
        await self.info.node.async_set_value(
            self.info.primary_value, new_value, options=options
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        tone_id: int | None = kwargs.get(ATTR_TONE)
        options = {}
        if (volume := kwargs.get(ATTR_VOLUME_LEVEL)) is not None:
            options["volume"] = round(volume * 100)
        # Play the default tone if a tone isn't provided
        if tone_id is None:
            await self.async_set_value(ToneID.DEFAULT, options)
            return

        await self.async_set_value(tone_id, options)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        await self.async_set_value(ToneID.OFF)
