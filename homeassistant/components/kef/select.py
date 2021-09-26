# examples:
# homeassistant/components/sisyphus/media_player.py
# homeassistant/components/plex/media_player.py
# homeassistant/components/renault/select.py
# homeassistant/components/panasonic_viera/__init__.py

"""Demo platform that offers a fake select entity."""
from __future__ import annotations

import logging

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.components.select import DOMAIN as SELECT_DOMAIN, SelectEntity
from homeassistant.const import CONF_HOST, DEVICE_DEFAULT_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DOMAIN
from .media_player import KefMediaPlayer

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType = None,
) -> None:
    """Set up the demo Select entity."""
    if discovery_info is None:
        return
    if not hass.data[DOMAIN]:
        _LOGGER.debug("No speakers online yet")
        raise PlatformNotReady()

    host = discovery_info[CONF_HOST]
    data = hass.data[DOMAIN][host]

    selects = data.setdefault(SELECT_DOMAIN, {})
    speaker = data[MEDIA_PLAYER_DOMAIN]

    if speaker._dsp is None:
        await speaker.update_dsp()

    for name, dsp_attr, options in (
        ["Bass Extension", "bass_extension", ["Standard", "Less", "Extra"]],
        ["Sub Polarity", "sub_polarity", ["-", "+"]],
    ):
        bass_extension = MediaSelect(
            unique_id=f"{speaker._unique_id}_{dsp_attr}",
            name=f"{speaker.name} {name}",
            icon="mdi:equalizer",
            current_option=speaker._dsp[dsp_attr],
            options=options,
            speaker=speaker,
            dsp_attr=dsp_attr,
        )
        selects[dsp_attr] = bass_extension

    async_add_entities(list(selects.values()))


class MediaSelect(SelectEntity):
    """Representation of a demo select entity."""

    _attr_should_poll = False

    def __init__(
        self,
        unique_id: str,
        name: str,
        icon: str,
        current_option: str | None,
        options: list[str],
        speaker: KefMediaPlayer,
        dsp_attr: str,
    ) -> None:
        """Initialize the Demo select entity."""
        self._speaker = speaker
        self._dsp_attr = dsp_attr
        self._attr_unique_id = unique_id
        self._attr_name = name or DEVICE_DEFAULT_NAME
        self._attr_current_option = current_option
        self._attr_icon = icon
        self._attr_options = options
        self._attr_device_info = {
            "identifiers": {(DOMAIN, unique_id)},
            "name": name,
        }

    async def async_select_option(self, option: str) -> None:
        """Update the current selected option."""
        self._attr_current_option = option
        await self._speaker.set_mode(**{self._dsp_attr: option})
        self.async_write_ha_state()

    async def async_update(self, **kwargs):
        """Update the select entity with the latest DSP settings."""
        self._attr_current_option = self._speaker._dsp[self._dsp_attr]
        self.async_write_ha_state()
