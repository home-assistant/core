"""Support for Xiaomi curtain."""

from typing import Any

from homeassistant.components.cover import ATTR_POSITION, CoverEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, GATEWAYS_KEY
from .entity import XiaomiDevice

ATTR_CURTAIN_LEVEL = "curtain_level"

DATA_KEY_PROTO_V1 = "status"
DATA_KEY_PROTO_V2 = "curtain_status"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Perform the setup for Xiaomi devices."""
    entities = []
    gateway = hass.data[DOMAIN][GATEWAYS_KEY][config_entry.entry_id]
    for device in gateway.devices["cover"]:
        model = device["model"]
        if model in ("curtain", "curtain.aq2", "curtain.hagl04"):
            if "proto" not in device or int(device["proto"][0:1]) == 1:
                data_key = DATA_KEY_PROTO_V1
            else:
                data_key = DATA_KEY_PROTO_V2
            entities.append(
                XiaomiGenericCover(device, "Curtain", data_key, gateway, config_entry)
            )
    async_add_entities(entities)


class XiaomiGenericCover(XiaomiDevice, CoverEntity):
    """Representation of a XiaomiGenericCover."""

    def __init__(self, device, name, data_key, xiaomi_hub, config_entry):
        """Initialize the XiaomiGenericCover."""
        self._data_key = data_key
        self._pos = 0
        super().__init__(device, name, xiaomi_hub, config_entry)

    @property
    def current_cover_position(self) -> int:
        """Return the current position of the cover."""
        return self._pos

    @property
    def is_closed(self) -> bool:
        """Return if the cover is closed."""
        return self.current_cover_position <= 0

    def close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        self._write_to_hub(self._sid, **{self._data_key: "close"})

    def open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        self._write_to_hub(self._sid, **{self._data_key: "open"})

    def stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        self._write_to_hub(self._sid, **{self._data_key: "stop"})

    def set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        position = kwargs.get(ATTR_POSITION)
        if self._data_key == DATA_KEY_PROTO_V2:
            self._write_to_hub(self._sid, **{ATTR_CURTAIN_LEVEL: position})
        else:
            self._write_to_hub(self._sid, **{ATTR_CURTAIN_LEVEL: str(position)})

    def parse_data(self, data, raw_data):
        """Parse data sent by gateway."""
        if ATTR_CURTAIN_LEVEL in data:
            self._pos = int(data[ATTR_CURTAIN_LEVEL])
            return True
        return False
