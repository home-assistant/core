"""Support for Velbus devices."""
import asyncio
import logging

import velbus
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

from .const import CONF_MEMO_TEXT, DOMAIN, SERVICE_SET_MEMO_TEXT

_LOGGER = logging.getLogger(__name__)

VELBUS_MESSAGE = "velbus.message"

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema({vol.Required(CONF_PORT): cv.string})}, extra=vol.ALLOW_EXTRA
)

PLATFORMS = ["switch", "sensor", "binary_sensor", "cover", "climate", "light"]


async def async_setup(hass, config):
    """Set up the Velbus platform."""
    # Import from the configuration file if needed
    if DOMAIN not in config:
        return True
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


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Establish connection with velbus."""

    def callback():
        modules = controller.get_modules()
        discovery_info = {"cntrl": controller}
        for platform in PLATFORMS:
            discovery_info[platform] = []
        for module in modules:
            for channel in range(1, module.number_of_channels() + 1):
                for platform in PLATFORMS:
                    if platform in module.get_categories(channel):
                        discovery_info[platform].append(
                            (module.get_module_address(), channel)
                        )
        hass.data[DOMAIN][entry.entry_id] = discovery_info

        for platform in PLATFORMS:
            hass.add_job(hass.config_entries.async_forward_entry_setup(entry, platform))

    try:
        controller = velbus.Controller(entry.data[CONF_PORT])
        controller.scan(callback)
    except velbus.util.VelbusException as err:
        _LOGGER.error("An error occurred: %s", err)
        raise ConfigEntryNotReady from err

    def syn_clock(self, service=None):
        try:
            controller.sync_clock()
        except velbus.util.VelbusException as err:
            _LOGGER.error("An error occurred: %s", err)

    hass.services.async_register(DOMAIN, "sync_clock", syn_clock, schema=vol.Schema({}))

    def set_memo_text(service):
        """Handle Memo Text service call."""
        module_address = service.data[CONF_ADDRESS]
        memo_text = service.data[CONF_MEMO_TEXT]
        memo_text.hass = hass
        try:
            controller.get_module(module_address).set_memo_text(
                memo_text.async_render()
            )
        except velbus.util.VelbusException as err:
            _LOGGER.error("An error occurred while setting memo text: %s", err)

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
    await asyncio.wait(
        [
            hass.config_entries.async_forward_entry_unload(entry, platform)
            for platform in PLATFORMS
        ]
    )
    hass.data[DOMAIN][entry.entry_id]["cntrl"].stop()
    hass.data[DOMAIN].pop(entry.entry_id)
    if not hass.data[DOMAIN]:
        hass.data.pop(DOMAIN)
    return True


class VelbusEntity(Entity):
    """Representation of a Velbus entity."""

    def __init__(self, module, channel):
        """Initialize a Velbus entity."""
        self._module = module
        self._channel = channel

    @property
    def unique_id(self):
        """Get unique ID."""
        serial = 0
        if self._module.serial == 0:
            serial = self._module.get_module_address()
        else:
            serial = self._module.serial
        return f"{serial}-{self._channel}"

    @property
    def name(self):
        """Return the display name of this entity."""
        return self._module.get_name(self._channel)

    @property
    def should_poll(self):
        """Disable polling."""
        return False

    async def async_added_to_hass(self):
        """Add listener for state changes."""
        self._module.on_status_update(self._channel, self._on_update)

    def _on_update(self, state):
        self.schedule_update_ha_state()

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "identifiers": {
                (DOMAIN, self._module.get_module_address(), self._module.serial)
            },
            "name": "{} ({})".format(
                self._module.get_module_name(), self._module.get_module_address()
            ),
            "manufacturer": "Velleman",
            "model": self._module.get_module_type_name(),
            "sw_version": "{}.{}-{}".format(
                self._module.memory_map_version,
                self._module.build_year,
                self._module.build_week,
            ),
        }
