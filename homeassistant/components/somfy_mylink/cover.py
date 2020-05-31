"""Cover Platform for the Somfy MyLink component."""
import logging

from homeassistant.components.cover import ENTITY_ID_FORMAT, CoverEntity
from homeassistant.util import slugify

from . import CONF_DEFAULT_REVERSE, DATA_SOMFY_MYLINK

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Discover and configure Somfy covers."""
    if discovery_info is None:
        return
    somfy_mylink = hass.data[DATA_SOMFY_MYLINK]
    cover_list = []
    try:
        mylink_status = await somfy_mylink.status_info()
    except TimeoutError:
        _LOGGER.error(
            "Unable to connect to the Somfy MyLink device, "
            "please check your settings"
        )
        return
    for cover in mylink_status["result"]:
        entity_id = ENTITY_ID_FORMAT.format(slugify(cover["name"]))
        entity_config = discovery_info.get(entity_id, {})
        default_reverse = discovery_info[CONF_DEFAULT_REVERSE]
        cover_config = {}
        cover_config["target_id"] = cover["targetID"]
        cover_config["name"] = cover["name"]
        cover_config["reverse"] = entity_config.get("reverse", default_reverse)
        cover_list.append(SomfyShade(somfy_mylink, **cover_config))
        _LOGGER.info(
            "Adding Somfy Cover: %s with targetID %s",
            cover_config["name"],
            cover_config["target_id"],
        )
    async_add_entities(cover_list)


class SomfyShade(CoverEntity):
    """Object for controlling a Somfy cover."""

    def __init__(
        self,
        somfy_mylink,
        target_id,
        name="SomfyShade",
        reverse=False,
        device_class="window",
    ):
        """Initialize the cover."""
        self.somfy_mylink = somfy_mylink
        self._target_id = target_id
        self._name = name
        self._reverse = reverse
        self._device_class = device_class

    @property
    def unique_id(self):
        """Return the unique ID of this cover."""
        return self._target_id

    @property
    def name(self):
        """Return the name of the cover."""
        return self._name

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        return None

    @property
    def assumed_state(self):
        """Let HA know the integration is assumed state."""
        return True

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return self._device_class

    async def async_open_cover(self, **kwargs):
        """Wrap Homeassistant calls to open the cover."""
        if not self._reverse:
            await self.somfy_mylink.move_up(self._target_id)
        else:
            await self.somfy_mylink.move_down(self._target_id)

    async def async_close_cover(self, **kwargs):
        """Wrap Homeassistant calls to close the cover."""
        if not self._reverse:
            await self.somfy_mylink.move_down(self._target_id)
        else:
            await self.somfy_mylink.move_up(self._target_id)

    async def async_stop_cover(self, **kwargs):
        """Stop the cover."""
        await self.somfy_mylink.move_stop(self._target_id)
