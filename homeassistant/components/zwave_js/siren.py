"""Support for Z-Wave controls using the siren platform."""
from __future__ import annotations

from typing import Any

from zwave_js_server.client import Client as ZwaveClient
from zwave_js_server.const.command_class.sound_switch import ToneID
from zwave_js_server.model.driver import Driver

from homeassistant.components.siren import (
    ATTR_TONE,
    ATTR_VOLUME_LEVEL,
    DOMAIN as SIREN_DOMAIN,
    SirenEntity,
    SirenEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_CLIENT, DOMAIN
from .discovery import ZwaveDiscoveryInfo
from .entity import ZWaveBaseEntity

PARALLEL_UPDATES = 0


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
        driver = client.driver
        assert driver is not None  # Driver is ready before platforms are loaded.
        entities: list[ZWaveBaseEntity] = []
        entities.append(ZwaveSirenEntity(config_entry, driver, info))
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
        self, config_entry: ConfigEntry, driver: Driver, info: ZwaveDiscoveryInfo
    ) -> None:
        """Initialize a ZwaveSirenEntity entity."""
        super().__init__(config_entry, driver, info)
        # Entity class attributes
        self._attr_available_tones = {
            int(id): val for id, val in self.info.primary_value.metadata.states.items()
        }
        self._attr_supported_features = (
            SirenEntityFeature.TURN_ON
            | SirenEntityFeature.TURN_OFF
            | SirenEntityFeature.VOLUME_SET
        )
        if self._attr_available_tones:
            self._attr_supported_features |= SirenEntityFeature.TONES

    @property
    def is_on(self) -> bool | None:
        """Return whether device is on."""
        if self.info.primary_value.value is None:
            return None
        return bool(self.info.primary_value.value)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        tone_id: int | None = kwargs.get(ATTR_TONE)
        options = {}
        if (volume := kwargs.get(ATTR_VOLUME_LEVEL)) is not None:
            options["volume"] = round(volume * 100)
        # Play the default tone if a tone isn't provided
        if tone_id is None:
            await self._async_set_value(
                self.info.primary_value, ToneID.DEFAULT, options
            )
            return

        await self._async_set_value(self.info.primary_value, tone_id, options)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        await self._async_set_value(self.info.primary_value, ToneID.OFF)
