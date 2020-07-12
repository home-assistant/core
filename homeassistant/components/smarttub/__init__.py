"""Example Load Platform integration."""
import logging

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.helpers.entity import Entity
from homeassistant.util import slugify

from .api import SmartTubAPI
from .const import DOMAIN, SMARTTUB_API

_LOGGER = logging.getLogger(__name__)

# TODO: light, switch, ...
PLATFORMS = ["sensor"]


async def async_setup(hass, config):
    """Set up smarttub component."""

    cfg = config.get(DOMAIN)
    if cfg is None:
        return True

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=cfg,
        )
    )

    return True


async def async_setup_entry(hass, entry):
    """Set up a smarttub config entry."""

    st = SmartTubAPI(hass, entry)
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.unique_id] = {
        SMARTTUB_API: st,
    }

    await st.async_setup()

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    return True


class SmartTubEntity(Entity):
    """Base class for SmartTub entities."""

    def __init__(self, api: SmartTubAPI, spa_id, entity_name):
        """Initialize the entity.

        Given a spa id and a short name for the entity, we provide basic device
        info, name, unique id, etc. for all derived entities.

        Also takes care of wiring up updates from SmartTubAPI
        """

        self.api = api
        self.spa_id = spa_id
        self._entity_name = entity_name

    @property
    def device_info(self) -> str:
        """Return device info."""
        return {"identifiers": {(DOMAIN, self.spa_id)}}

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        spa_name = self.api.get_spa_name(self.spa_id)
        return f"{spa_name} {self._entity_name}"

    @property
    def unique_id(self) -> str:
        """Return a unique id for the entity."""
        return f"{self.spa_id}-{slugify(self._entity_name)}"

    @property
    def should_poll(self) -> bool:
        """Indicate whether polling is desired."""
        # SmartTubAPI handles polling
        return False

    @property
    def available(self) -> bool:
        """Indicate whether this entity is available."""
        return self.api.entity_is_available(self)

    async def async_update(self):
        """Update the state of this entity."""
        await self.api.async_update_entity(self)

    async def async_added_to_hass(self):
        """Register callback for state updates."""
        await self.api.async_register_entity(self)
