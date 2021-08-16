"""Support for Velbus devices."""
import logging

from velbusaio.controller import Velbus
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

from .const import CONF_MEMO_TEXT, DOMAIN, SERVICE_SET_MEMO_TEXT

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema({vol.Required(CONF_PORT): cv.string})}, extra=vol.ALLOW_EXTRA
)

PLATFORMS = ["switch", "sensor", "binary_sensor", "cover", "climate", "light"]


async def async_setup(hass, config):
    """Set up the Velbus platform."""
    # Import from the configuration file if needed
    if DOMAIN not in config:
        return True

    _LOGGER.warning("Loading VELBUS via configuration.yaml is deprecated")

    port = config[DOMAIN].get(CONF_PORT)
    data = {}

    if port:
        data = {CONF_PORT: port, CONF_NAME: "Velbus import"}
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=data
        )
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Establish connection with velbus."""
    hass.data.setdefault(DOMAIN, {})

    controller = Velbus(entry.data[CONF_PORT])
    hass.data[DOMAIN][entry.entry_id] = controller
    await controller.connect()

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    async def scan(self, service=None):
        await controller.scan()

    hass.services.async_register(DOMAIN, "scan", scan)

    async def syn_clock(self, service=None):
        await controller.sync_clock()

    hass.services.async_register(DOMAIN, "sync_clock", syn_clock)

    def set_memo_text(service):
        """Handle Memo Text service call."""
        module_address = service.data[CONF_ADDRESS]
        memo_text = service.data[CONF_MEMO_TEXT]
        memo_text.hass = hass
        controller.get_module(module_address).set_memo_text(memo_text.async_render())

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_MEMO_TEXT,
        set_memo_text,
        vol.Schema(
            {
                vol.Required(CONF_ADDRESS): vol.All(
                    vol.Coerce(int), vol.Range(min=0, max=255)
                ),
                vol.Optional(CONF_MEMO_TEXT, default=""): cv.template,
            }
        ),
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Remove the velbus connection."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    await hass.data[DOMAIN][entry.entry_id].stop()
    hass.data[DOMAIN].pop(entry.entry_id)
    if not hass.data[DOMAIN]:
        hass.data.pop(DOMAIN)
    return unload_ok


class VelbusEntity(Entity):
    """Representation of a Velbus entity."""

    def __init__(self, channel):
        """Initialize a Velbus entity."""
        self._channel = channel

    @property
    def unique_id(self):
        """Get unique ID."""
        return "{}.{}.{}".format(
            self._channel.get_module_type(),
            self._channel.get_module_address(),
            self._channel.get_channel_number(),
        )

    @property
    def name(self):
        """Return the display name of this entity."""
        return self._channel.get_name()

    @property
    def should_poll(self):
        """Disable polling."""
        return False

    async def async_added_to_hass(self):
        """Add listener for state changes."""
        self._channel.on_status_update(self._on_update)

    async def _on_update(self):
        self.async_write_ha_state()

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "identifiers": {
                (
                    DOMAIN,
                    self._channel.get_module_address(),
                    self._channel.get_module_serial(),
                )
            },
            "name": self._channel.get_full_name(),
            "manufacturer": "Velleman",
            "model": self._channel.get_module_type_name(),
            "sw_version": self._channel.get_module_sw_version(),
        }
