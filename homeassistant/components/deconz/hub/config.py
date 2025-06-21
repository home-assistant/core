"""deCONZ config entry abstraction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Self

from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_PORT

from ..const import (
    CONF_ALLOW_CLIP_SENSOR,
    CONF_ALLOW_DECONZ_GROUPS,
    CONF_ALLOW_NEW_DEVICES,
    DEFAULT_ALLOW_CLIP_SENSOR,
    DEFAULT_ALLOW_DECONZ_GROUPS,
    DEFAULT_ALLOW_NEW_DEVICES,
)

if TYPE_CHECKING:
    from .. import DeconzConfigEntry


@dataclass
class DeconzConfig:
    """Represent a deCONZ config entry."""

    entry: DeconzConfigEntry

    host: str
    port: int
    api_key: str

    allow_clip_sensor: bool
    allow_deconz_groups: bool
    allow_new_devices: bool

    @classmethod
    def from_config_entry(cls, config_entry: DeconzConfigEntry) -> Self:
        """Create object from config entry."""
        config = config_entry.data
        options = config_entry.options
        return cls(
            entry=config_entry,
            host=config[CONF_HOST],
            port=config[CONF_PORT],
            api_key=config[CONF_API_KEY],
            allow_clip_sensor=options.get(
                CONF_ALLOW_CLIP_SENSOR,
                DEFAULT_ALLOW_CLIP_SENSOR,
            ),
            allow_deconz_groups=options.get(
                CONF_ALLOW_DECONZ_GROUPS,
                DEFAULT_ALLOW_DECONZ_GROUPS,
            ),
            allow_new_devices=options.get(
                CONF_ALLOW_NEW_DEVICES,
                DEFAULT_ALLOW_NEW_DEVICES,
            ),
        )
