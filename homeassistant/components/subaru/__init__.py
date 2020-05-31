"""The Subaru integration."""
import asyncio
from collections import defaultdict
from datetime import datetime
import logging

from subarulink.hass import HassController as SubaruAPI, SubaruException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_BATTERY_LEVEL,
    CONF_DEVICE_ID,
    CONF_PASSWORD,
    CONF_PIN,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.entity import Entity
from homeassistant.util import slugify

from .const import (
    CONF_HARD_POLL_INTERVAL,
    DEFAULT_HARD_POLL_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    ICONS,
    SUBARU_COMPONENTS,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, base_config):
    """Set up of Subaru component."""
    return True


async def async_setup_entry(hass, entry):
    """Set up Subaru from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    config = entry.data
    websession = aiohttp_client.async_get_clientsession(hass)
    date = datetime.now().strftime("%Y-%m-%d")
    device_name = "Home Assistant: Added " + date
    try:
        controller = SubaruAPI(
            websession,
            config[CONF_USERNAME],
            config[CONF_PASSWORD],
            config[CONF_DEVICE_ID],
            config[CONF_PIN],
            device_name,
            update_interval=entry.options.get(
                CONF_HARD_POLL_INTERVAL, DEFAULT_HARD_POLL_INTERVAL
            ),
            fetch_interval=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )
        if not await controller.connect():
            _LOGGER.error("Failed to connect")
            return False
    except SubaruException as ex:
        _LOGGER.error("Unable to communicate with Subaru API: %s", ex.message)
        return False
    entry_data = hass.data[DOMAIN][entry.entry_id] = {
        "controller": controller,
        "devices": defaultdict(list),
        "listener": [entry.add_update_listener(update_listener)],
    }

    all_devices = entry_data["controller"].get_homeassistant_components()

    if not all_devices:
        return False

    for device in all_devices:
        entry_data["devices"][device.hass_type].append(device)

    for component in SUBARU_COMPONENTS:
        _LOGGER.debug("Loading %s", component)
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in SUBARU_COMPONENTS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    if len(hass.data[DOMAIN]) == 0:
        hass.data.pop(DOMAIN)

    return unload_ok


async def update_listener(hass, config_entry):
    """Update when config_entry options update."""
    controller = hass.data[DOMAIN][config_entry.entry_id]["controller"]
    controller.set_update_interval(config_entry.options.get(CONF_HARD_POLL_INTERVAL))
    controller.set_fetch_interval(config_entry.options.get(CONF_SCAN_INTERVAL))


class SubaruDevice(Entity):
    """Representation of a Subaru Device."""

    def __init__(self, subaru_device, controller, config_entry):
        """Initialize the Subaru Device."""
        self.subaru_device = subaru_device
        self.controller = controller
        self.config_entry = config_entry
        self._name = self.subaru_device.name
        self.subaru_id = slugify(self.subaru_device.uniq_name)
        self._attributes = {}
        self._icon = ICONS.get(self.subaru_device.type)

    @property
    def name(self):
        """Return name."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self.subaru_id

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return self._icon

    @property
    def should_poll(self):
        """Return the polling state."""
        return self.subaru_device.should_poll

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        attr = self._attributes
        if self.subaru_device.has_battery():
            attr[ATTR_BATTERY_LEVEL] = self.subaru_device.battery_level()
        return attr

    @property
    def device_info(self):
        """Return the device_info of the device."""
        return {
            "identifiers": {(DOMAIN, self.subaru_device.id())},
            "name": self.subaru_device.car_name(),
            "manufacturer": "Subaru",
        }

    async def async_added_to_hass(self):
        """Register state update callback."""

    async def async_will_remove_from_hass(self):
        """Prepare for unload."""

    async def async_update(self):
        """Update the state of the device."""
        try:
            await self.subaru_device.async_update()
        except SubaruException as ex:
            _LOGGER.error(ex.message)
