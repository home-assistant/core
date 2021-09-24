"""Support for Velbus devices."""
from __future__ import annotations

import logging

from velbusaio.controller import Velbus
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

from .const import (
    CONF_INTERFACE,
    CONF_MEMO_TEXT,
    DOMAIN,
    SERVICE_SCAN,
    SERVICE_SET_MEMO_TEXT,
    SERVICE_SYNC,
)

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


async def velbus_connect_task(
    controller: Velbus, hass: HomeAssistant, entry_id: str
) -> None:
    """Task to offload the long running connect."""
    await controller.connect()


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Establish connection with velbus."""
    hass.data.setdefault(DOMAIN, {})

    controller = Velbus(
        entry.data[CONF_PORT],
        cache_dir=hass.config.path(".storage/velbuscache/"),
    )
    hass.data[DOMAIN][entry.entry_id] = {}
    hass.data[DOMAIN][entry.entry_id]["cntrl"] = controller
    hass.data[DOMAIN][entry.entry_id]["tsk"] = hass.async_create_task(
        velbus_connect_task(controller, hass, entry.entry_id)
    )

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    if hass.services.has_service(DOMAIN, SERVICE_SCAN):
        return True

    def check_entry_id(interface: str):
        for entry in hass.config_entries.async_entries(DOMAIN):
            if "port" in entry.data and entry.data["port"] == interface:
                return entry.entry_id
        raise vol.Invalid(
            "The interface provided is not defined as a port in a Velbus integration"
        )

    async def scan(call):
        await hass.data[DOMAIN][call.data[CONF_INTERFACE]]["cntrl"].scan()

    hass.services.async_register(
        DOMAIN,
        SERVICE_SCAN,
        scan,
        vol.Schema({vol.Required(CONF_INTERFACE): vol.All(cv.string, check_entry_id)}),
    )

    async def syn_clock(call):
        await hass.data[DOMAIN][call.data[CONF_INTERFACE]]["cntrl"].sync_clock()

    hass.services.async_register(
        DOMAIN,
        SERVICE_SYNC,
        syn_clock,
        vol.Schema({vol.Required(CONF_INTERFACE): vol.All(cv.string, check_entry_id)}),
    )

    async def set_memo_text(call):
        """Handle Memo Text service call."""
        memo_text = call.data[CONF_MEMO_TEXT]
        memo_text.hass = hass
        await hass.data[DOMAIN][call.data[CONF_INTERFACE]]["cntrl"].get_module(
            call.data[CONF_ADDRESS]
        ).set_memo_text(memo_text.async_render())

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_MEMO_TEXT,
        set_memo_text,
        vol.Schema(
            {
                vol.Required(CONF_INTERFACE): vol.All(cv.string, check_entry_id),
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
    await hass.data[DOMAIN][entry.entry_id]["cntrl"].stop()
    hass.data[DOMAIN].pop(entry.entry_id)
    if not hass.data[DOMAIN]:
        hass.data.pop(DOMAIN)
        hass.services.async_remove(DOMAIN, SERVICE_SCAN)
        hass.services.async_remove(DOMAIN, SERVICE_SYNC)
        hass.services.async_remove(DOMAIN, SERVICE_SET_MEMO_TEXT)
    return unload_ok


class VelbusEntity(Entity):
    """Representation of a Velbus entity."""

    def __init__(self, channel):
        """Initialize a Velbus entity."""
        self._channel = channel

    @property
    def unique_id(self):
        """Get unique ID."""
        if (serial := self._channel.get_module_serial()) == 0:
            serial = self._channel.get_module_address()
        return f"{serial}-{self._channel.get_channel_number()}"

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
