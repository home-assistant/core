"""Select platform that sets up DSP options for KEF Speakers."""
from __future__ import annotations

import logging
from typing import Any, cast

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.components.select import DOMAIN as SELECT_DOMAIN, SelectEntity
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DOMAIN
from .media_player import KefMediaPlayer

_LOGGER = logging.getLogger(__name__)


def str_to_option(option: str) -> Any:
    """Parse the option."""
    if option == "off":
        return False
    if option == "on":
        return True
    return option


def option_to_str(option) -> str:
    """Parse the option."""
    if option is False:
        return "off"
    if option is True:
        return "on"
    return option


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType = None,
) -> None:
    """Set up the KEF DSP select entity."""
    if discovery_info is None:
        return

    host = discovery_info[CONF_HOST]
    data = hass.data[DOMAIN][host]

    selects = data.setdefault(SELECT_DOMAIN, {})
    speaker = data[MEDIA_PLAYER_DOMAIN]

    if speaker.dsp is None:
        await speaker.update_dsp()

    for dsp_attr, options in (
        ["bass_extension", ["Standard", "Less", "Extra"]],
        ["sub_polarity", ["-", "+"]],
        ["desk_mode", ["on", "off"]],
        ["wall_mode", ["on", "off"]],
        ["phase_correction", ["on", "off"]],
        ["high_pass", ["on", "off"]],
    ):
        dsp_attr = cast(str, dsp_attr)
        name = dsp_attr.replace("_", " ")
        current_option = option_to_str(speaker.dsp[dsp_attr])  # type: ignore
        select = MediaSelect(
            unique_id=f"{speaker.unique_id}_{dsp_attr}",
            name=f"{speaker.name} {name}",
            icon="mdi:equalizer",
            current_option=current_option,
            options=cast(list[str], options),  # pylint: disable=unsubscriptable-object
            speaker=speaker,
            dsp_attr=dsp_attr,
        )
        selects[dsp_attr] = select

    async_add_entities(list(selects.values()))


class MediaSelect(SelectEntity):
    """Representation of a KEF DSP select entity."""

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
        """Initialize the KEF DSP select entity."""
        self._speaker = speaker
        self._dsp_attr = dsp_attr
        self._attr_unique_id = unique_id
        self._attr_name = name
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
        option = str_to_option(option)
        _LOGGER.debug(
            "Setting %s to %s (%s)", self._attr_name, option, self._attr_current_option
        )
        if option != "Unknown":
            self._attr_available = True
            await self._speaker.set_mode(**{self._dsp_attr: option})
        else:
            self._attr_available = False
        self.async_write_ha_state()

    async def async_update(self, **kwargs):
        """Update the select entity with the latest DSP settings."""
        self._attr_current_option = option_to_str(self._speaker.dsp[self._dsp_attr])
        self.async_write_ha_state()
