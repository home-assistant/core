"""Select platform that sets up DSP options for KEF Speakers."""
from __future__ import annotations

import logging

from aiokef.aiokef import DSP_OPTION_MAPPING

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN, NumberEntity
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
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
    """Set up the KEF DSP number entities."""
    if discovery_info is None:
        return

    host = discovery_info[CONF_HOST]
    data = hass.data[DOMAIN][host]

    numbers = data.setdefault(NUMBER_DOMAIN, {})
    speaker = data[MEDIA_PLAYER_DOMAIN]

    if speaker.dsp is None:
        await speaker.update_dsp()

    for dsp_attr, options in (
        ["desk_db", DSP_OPTION_MAPPING["desk_db"]],
        ["wall_db", DSP_OPTION_MAPPING["wall_db"]],
        ["treble_db", DSP_OPTION_MAPPING["treble_db"]],
        ["high_hz", DSP_OPTION_MAPPING["high_hz"]],
        ["low_hz", DSP_OPTION_MAPPING["low_hz"]],
        ["sub_db", DSP_OPTION_MAPPING["sub_db"]],
    ):
        name = dsp_attr.replace("_", " ")
        min_value = min(options)
        max_value = max(options)
        step = options[1] - options[0]
        select = KefDSPNumber(
            unique_id=f"{speaker.unique_id}_{dsp_attr}",
            name=f"{speaker.name} {name}",
            icon="mdi:equalizer",
            min_value=min_value,
            max_value=max_value,
            step=step,
            value=speaker.dsp[dsp_attr],  # type: ignore
            speaker=speaker,
            dsp_attr=dsp_attr,
        )
        numbers[dsp_attr] = select

    async_add_entities(list(numbers.values()))


class KefDSPNumber(NumberEntity):
    """Representation of a DSP number entity."""

    _attr_should_poll = False

    def __init__(
        self,
        unique_id: str,
        name: str,
        icon: str,
        min_value: float,
        max_value: float,
        step: float,
        value: float,
        speaker: KefMediaPlayer,
        dsp_attr: str,
    ) -> None:
        """Initialize the KEF DSP number entity."""
        self._speaker = speaker
        self._dsp_attr = dsp_attr
        self._attr_unique_id = unique_id
        self._attr_name = name

        self._attr_max_value = max_value
        self._attr_min_value = min_value
        self._attr_step = step
        self._attr_value = value

        self._attr_icon = icon
        self._attr_device_info = {
            "identifiers": {(DOMAIN, unique_id)},
            "name": name,
        }

    async def async_set_value(self, value: float) -> None:
        """Update the current selected value."""
        _LOGGER.debug("Setting %s to %s", self._attr_name, value)
        self._attr_value = value
        if value != "Unknown":  # type: ignore
            await getattr(self._speaker, f"set_{self._dsp_attr}")(value)
            self._attr_available = True
        else:
            self._attr_available = False
        self.async_write_ha_state()

    async def async_update(self, **kwargs):
        """Update the select entity with the latest DSP settings."""
        self._attr_value = self._speaker.dsp[self._dsp_attr]
        self.async_write_ha_state()
