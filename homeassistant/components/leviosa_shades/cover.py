"""The Leviosa Shades Zone base entity."""
import logging
from typing import Any

from leviosapy import LeviosaShadeGroup as tShadeGroup, LeviosaZoneHub as tZoneHub

from homeassistant.components import cover
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import BLIND_GROUPS, DEVICE_MAC, DOMAIN, MANUFACTURER, MODEL

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: cover.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Leviosa shade groups."""
    hub: tZoneHub = hass.data[DOMAIN][entry.entry_id]
    hub_mac = entry.data[DEVICE_MAC]
    blind_groups = entry.data[BLIND_GROUPS]
    _LOGGER.debug("Groups to create: %s", blind_groups)

    entities = []
    for blind_group in blind_groups:
        _LOGGER.debug("Adding blind_group: %s", blind_group)
        new_group_obj = hub.AddGroup(blind_group)
        entities.append(LeviosaBlindGroup(hass, hub_mac, new_group_obj))
    async_add_entities(entities)


class LeviosaBlindGroup(cover.CoverEntity):
    """Represents a Leviosa shade group entity."""

    _attr_device_class = cover.CoverDeviceClass.SHADE
    _attr_has_entity_name = True
    _attr_supported_features = (
        cover.CoverEntityFeature.OPEN
        | cover.CoverEntityFeature.CLOSE
        | cover.CoverEntityFeature.STOP
    )

    def __init__(
        self, hass: HomeAssistant, hub_mac: str, blind_group_obj: tShadeGroup
    ) -> None:
        """Initialize the shade group."""
        self._blind_group_id = f"{hub_mac}-{blind_group_obj.number}"
        self._blind_group_obj = blind_group_obj
        self._hass = hass

        self._attr_name = self._blind_group_obj.name
        self._attr_unique_id = self._blind_group_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, hub_mac)},
            name=self._blind_group_obj.Hub.name,
            manufacturer=MANUFACTURER,
            model=MODEL,
            via_device=(DOMAIN, self._blind_group_obj.Hub.hub_ip),
        )
        _LOGGER.debug(
            "Creating cover.%s, UID: %s",
            self._blind_group_obj.name,
            self._blind_group_id,
        )

    @property
    def assumed_state(self):
        """Indicate that we do not go to the device to know its state."""
        return True

    @property
    def is_closed(self) -> bool:
        """Is the blind group currently closed?."""
        return self._blind_group_obj.position == 0

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        await self._blind_group_obj.close()

    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        await self._blind_group_obj.open()

    async def async_stop_cover(self, **kwargs):
        """Stop the cover."""
        await self._blind_group_obj.stop()
