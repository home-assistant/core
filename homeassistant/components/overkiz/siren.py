"""Support for Overkiz sirens."""

from typing import Any

from pyoverkiz.enums import OverkizState
from pyoverkiz.enums.command import OverkizCommand, OverkizCommandParam

from homeassistant.components.siren import (
    ATTR_DURATION,
    SirenEntity,
    SirenEntityFeature,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import OverkizDataConfigEntry
from .entity import OverkizEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OverkizDataConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Overkiz sirens from a config entry."""
    data = entry.runtime_data

    async_add_entities(
        OverkizSiren(device.device_url, data.coordinator)
        for device in data.platforms[Platform.SIREN]
    )


class OverkizSiren(OverkizEntity, SirenEntity):
    """Representation an Overkiz Siren."""

    _attr_supported_features = (
        SirenEntityFeature.TURN_OFF
        | SirenEntityFeature.TURN_ON
        | SirenEntityFeature.DURATION
    )

    @property
    def is_on(self) -> bool:
        """Get whether the siren is in on state."""
        return (
            self.executor.select_state(OverkizState.CORE_ON_OFF)
            == OverkizCommandParam.ON
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Send the on command."""
        if kwargs.get(ATTR_DURATION):
            duration = kwargs[ATTR_DURATION]
        else:
            duration = 2 * 60  # 2 minutes

        duration_in_ms = duration * 1000

        await self.executor.async_execute_command(
            # https://www.tahomalink.com/enduser-mobile-web/steer-html5-client/vendor/somfy/io/siren/const.js
            OverkizCommand.RING_WITH_SINGLE_SIMPLE_SEQUENCE,
            duration_in_ms,  # duration
            75,  # 90 seconds bip, 30 seconds silence
            2,  # repeat 3 times
            OverkizCommandParam.MEMORIZED_VOLUME,
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Send the off command."""
        await self.executor.async_execute_command(OverkizCommand.OFF)
