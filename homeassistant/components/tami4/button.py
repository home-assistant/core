"""Button entities for Tami4Edge."""
import logging

from Tami4EdgeAPI import Tami4EdgeAPI

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import API, DOMAIN
from .entity import Tami4EdgeBaseEntity

_LOGGER = logging.getLogger(__name__)

ENTITY_DESCRIPTION = ButtonEntityDescription(
    key="boil_water",
    translation_key="boil_water",
    icon="mdi:kettle-steam",
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Perform the setup for Tami4Edge."""
    data = hass.data[DOMAIN][entry.entry_id]
    api: Tami4EdgeAPI = data[API]

    entity = Tami4EdgeBoilButton(api)

    async_add_entities([entity])


class Tami4EdgeBoilButton(Tami4EdgeBaseEntity, ButtonEntity):
    """Boil button entity for Tami4Edge."""

    def __init__(self, api: Tami4EdgeAPI) -> None:
        """Initialize the button entity."""
        Tami4EdgeBaseEntity.__init__(self, api, ENTITY_DESCRIPTION)

    def press(self) -> None:
        """Handle the button press."""
        self._api.boil_water()
