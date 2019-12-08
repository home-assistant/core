"""Support for Tesla cars."""
import asyncio
from collections import defaultdict
import logging

from teslajsonpy import Controller as TeslaAPI, TeslaException
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    ATTR_BATTERY_LEVEL,
    CONF_ACCESS_TOKEN,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_TOKEN,
    CONF_USERNAME,
)
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client, config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_call_later
from homeassistant.util import slugify

from .config_flow import (
    CannotConnect,
    InvalidAuth,
    configured_instances,
    validate_input,
)
from .const import DATA_LISTENER, DOMAIN, TESLA_COMPONENTS

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Optional(CONF_SCAN_INTERVAL, default=300): vol.All(
                    cv.positive_int, vol.Clamp(min=300)
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


@callback
def _async_save_tokens(hass, config_entry, access_token, refresh_token):
    hass.config_entries.async_update_entry(
        config_entry,
        data={
            **config_entry.data,
            CONF_ACCESS_TOKEN: access_token,
            CONF_TOKEN: refresh_token,
        },
    )


async def async_setup(hass, base_config):
    """Set up of Tesla component."""

    def _update_entry(email, data=None, options=None):
        data = data or {}
        options = options or {CONF_SCAN_INTERVAL: 300}
        for entry in hass.config_entries.async_entries(DOMAIN):
            if email != entry.title:
                continue
            hass.config_entries.async_update_entry(entry, data=data, options=options)

    config = base_config.get(DOMAIN)
    if not config:
        return True
    email = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]
    scan_interval = config[CONF_SCAN_INTERVAL]
    if email in configured_instances(hass):
        try:
            info = await validate_input(hass, config)
        except (CannotConnect, InvalidAuth):
            return False
        _update_entry(
            email,
            data={
                CONF_ACCESS_TOKEN: info[CONF_ACCESS_TOKEN],
                CONF_TOKEN: info[CONF_TOKEN],
            },
            options={CONF_SCAN_INTERVAL: scan_interval},
        )
    else:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data={CONF_USERNAME: email, CONF_PASSWORD: password},
            )
        )
        async_call_later(
            hass,
            15,
            lambda _: _update_entry(email, options={CONF_SCAN_INTERVAL: scan_interval}),
        )
    return True


async def async_setup_entry(hass, config_entry):
    """Set up Tesla as config entry."""

    if DOMAIN not in hass.data or config_entry.entry_id not in hass.data[DOMAIN]:
        config = config_entry.data
        hass.data.setdefault(DOMAIN, {})

        try:
            websession = aiohttp_client.async_get_clientsession(hass)
            controller = TeslaAPI(
                websession,
                refresh_token=config[CONF_TOKEN],
                update_interval=config_entry.options.get(CONF_SCAN_INTERVAL, 300),
            )
            (refresh_token, access_token) = await controller.connect()
        except TeslaException as ex:
            _LOGGER.error("Unable to communicate with Tesla API: %s", ex.message)
            return False
        _async_save_tokens(hass, config_entry, access_token, refresh_token)
        entry_data = hass.data[DOMAIN][config_entry.entry_id] = {
            "controller": controller,
            "devices": defaultdict(list),
            DATA_LISTENER: [config_entry.add_update_listener(update_listener)],
        }
        _LOGGER.debug("Connected to the Tesla API.")

    all_devices = entry_data["controller"].get_homeassistant_components()

    if not all_devices:
        return False

    for device in all_devices:
        entry_data["devices"][device.hass_type].append(device)

    for component in TESLA_COMPONENTS:
        _LOGGER.debug("Loading %s", component)
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, component)
        )
    return True


async def async_unload_entry(hass, config_entry) -> bool:
    """Unload a config entry."""
    await asyncio.gather(
        *[
            hass.config_entries.async_forward_entry_unload(config_entry, component)
            for component in TESLA_COMPONENTS
        ]
    )
    for listener in hass.data[DOMAIN][config_entry.entry_id][DATA_LISTENER]:
        listener()
    username = config_entry.title
    hass.data[DOMAIN].pop(config_entry.entry_id)
    _LOGGER.debug("Unloaded entry for %s", username)
    return True


async def update_listener(hass, config_entry):
    """Update when config_entry options update."""
    controller = hass.data[DOMAIN][config_entry.entry_id]["controller"]
    old_update_interval = controller.update_interval
    controller.update_interval = config_entry.options.get(CONF_SCAN_INTERVAL)
    _LOGGER.debug(
        "Changing scan_interval from %s to %s",
        old_update_interval,
        controller.update_interval,
    )


class TeslaDevice(Entity):
    """Representation of a Tesla device."""

    def __init__(self, tesla_device, controller, config_entry):
        """Initialise the Tesla device."""
        self.tesla_device = tesla_device
        self.controller = controller
        self.config_entry = config_entry
        self._name = self.tesla_device.name
        self.tesla_id = slugify(self.tesla_device.uniq_name)
        self._attributes = {}

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self.tesla_id

    @property
    def should_poll(self):
        """Return the polling state."""
        return self.tesla_device.should_poll

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        attr = self._attributes
        if self.tesla_device.has_battery():
            attr[ATTR_BATTERY_LEVEL] = self.tesla_device.battery_level()
        return attr

    @property
    def device_info(self):
        """Return the device_info of the device."""
        return {
            "identifiers": {(DOMAIN, self.tesla_device.id())},
            "name": self.tesla_device.car_name(),
            "manufacturer": "Tesla",
            "model": self.tesla_device.car_type,
            "sw_version": self.tesla_device.car_version,
        }

    async def async_added_to_hass(self):
        """Register state update callback."""
        pass

    async def async_will_remove_from_hass(self):
        """Prepare for unload."""
        pass

    async def async_update(self):
        """Update the state of the device."""
        if self.controller.is_token_refreshed():
            (refresh_token, access_token) = self.controller.get_tokens()
            _async_save_tokens(
                self.hass, self.config_entry, access_token, refresh_token
            )
            _LOGGER.debug("Saving new tokens in config_entry")
        await self.tesla_device.async_update()
