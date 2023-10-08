"""The Leviosa Shades Zone base entity."""
import logging

from leviosapy import LeviosaShadeGroup as tShadeGroup, LeviosaZoneHub as tZoneHub
import voluptuous as vol

from homeassistant.components import cover
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    BLIND_GROUPS,
    DOMAIN,
    MANUFACTURER,
    MODEL,
    SERVICE_NEXT_DOWN_POS,
    SERVICE_NEXT_UP_POS,
)

_LOGGER = logging.getLogger(__name__)

# Estimated time it takes to complete a transition
# from one state to another
TRANSITION_COMPLETE_DURATION = 30
PARALLEL_UPDATES = 1

COVER_NEXT_POS_SCHEMA = vol.Schema({vol.Optional(ATTR_ENTITY_ID): cv.entity_ids})


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Leviosa shade groups."""
    _LOGGER.debug(
        "Setting up %s[%s]: %s",
        entry.domain,
        entry.title,
        entry.entry_id,
    )
    hub_name = entry.title
    hub_mac = entry.data["device_mac"]
    hub_ip = entry.data["host"]
    blind_groups = entry.data[BLIND_GROUPS]
    _LOGGER.debug("Groups to create: %s", blind_groups)
    hub = tZoneHub(
        hub_ip=hub_ip, hub_name=hub_name, websession=async_get_clientsession(hass)
    )
    await hub.getHubInfo()  # Check all is good
    _LOGGER.debug("Hub object created, FW: %s", hub.fwVer)
    entities = []
    for blind_group in blind_groups:
        _LOGGER.debug("Adding blind_group: %s", blind_group)
        new_group_obj = hub.AddGroup(blind_group)
        entities.append(
            LeviosaBlindGroup(
                hass, hub_mac + "-" + str(new_group_obj.number), new_group_obj
            )
        )
    async_add_entities(entities)

    _LOGGER.debug("Setting up Leviosa shade group services")
    platform = entity_platform.current_platform.get()
    platform.async_register_entity_service(
        SERVICE_NEXT_DOWN_POS,
        COVER_NEXT_POS_SCHEMA,
        "next_down_pos",
    )
    platform.async_register_entity_service(
        SERVICE_NEXT_UP_POS,
        COVER_NEXT_POS_SCHEMA,
        "next_up_pos",
    )


class LeviosaBlindGroup(cover.CoverEntity):
    """Represents a Leviosa shade group entity."""

    def __init__(
        self, hass: HomeAssistant, blind_group_id, blind_group_obj: tShadeGroup
    ) -> None:
        """Initialize the shade group."""
        self._blind_group_id = blind_group_id
        self._blind_group_obj = blind_group_obj
        self._hass = hass
        _LOGGER.debug(
            "Creating cover.%s, UID: %s",
            self._blind_group_obj.name,
            self._blind_group_id,
        )

    @property
    def name(self):
        """Name of the device."""
        return self._blind_group_obj.name

    @property
    def unique_id(self):
        """Return a unique ID for this device."""

        return self._blind_group_id

    @property
    def assumed_state(self):
        """Indicate that we do not go to the device to know its state."""

        return False

    @property
    def current_cover_position(self):
        """Indicate that we do not go to the device to know its state."""
        return self._blind_group_obj.position

    @property
    def should_poll(self):
        """Indicate that the device does not respond to polling."""

        return True

    @property
    def supported_features(self):
        """Bitmap indicating which features this device supports."""

        return cover.SUPPORT_OPEN | cover.SUPPORT_CLOSE | cover.SUPPORT_STOP

    @property
    def device_class(self):
        """Indicate we're managing a Roller blind motor group."""

        return cover.DEVICE_CLASS_SHADE

    @property
    def device_info(self):
        """Return the device_info of the device."""

        device_info = {
            "identifiers": {(DOMAIN, self._blind_group_obj.Hub.hub_ip)},
            "name": self._blind_group_obj.Hub.name,
            "manufacturer": MANUFACTURER,
            "model": MODEL,
            "via_device": (DOMAIN, self._blind_group_obj.Hub.hub_ip),
        }

        return device_info

    @property
    def is_opening(self):
        """Is the blind group opening?."""

        return False

    @property
    def is_closing(self):
        """Is the blind closing?."""

        return False

    @property
    def is_closed(self):
        """Is the blind group currently closed?."""
        return self._blind_group_obj.position == 0

    async def async_close_cover(self, **kwargs):
        """Close the cover."""
        await self._blind_group_obj.close()

    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        await self._blind_group_obj.open()

    async def async_stop_cover(self, **kwargs):
        """Stop the cover."""
        await self._blind_group_obj.stop()

    async def next_down_pos(self):
        """Move to the next position down."""
        await self._blind_group_obj.down()

    async def next_up_pos(self):
        """Move to the next position down."""
        await self._blind_group_obj.up()
