"""Support for Tesla cars."""
from collections import defaultdict
import logging

from teslajsonpy import Controller as teslaAPI, TeslaException
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
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client, config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import slugify

from .config_flow import configured_instances
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
def _async_save_refresh_token(hass, config_entry, access_token, token):
    hass.config_entries.async_update_entry(
        config_entry,
        data={**config_entry.data, CONF_ACCESS_TOKEN: access_token, CONF_TOKEN: token},
    )


async def async_setup(hass, base_config):
    """Set up of Tesla component."""
    config = base_config.get(DOMAIN)
    if not config:
        return True
    email = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    if email in configured_instances(hass):
        for entry in hass.config_entries.async_entries(DOMAIN):
            if email == entry.title:
                try:
                    websession = aiohttp_client.async_get_clientsession(hass)
                    controller = teslaAPI(
                        websession, email=email, password=password, update_interval=300
                    )
                    (refresh_token, access_token) = await controller.connect(
                        test_login=True
                    )
                    hass.config_entries.async_update_entry(
                        entry,
                        data={
                            CONF_ACCESS_TOKEN: access_token,
                            CONF_TOKEN: refresh_token,
                        },
                    )
                except TeslaException as ex:
                    _LOGGER.warning(
                        "Configuration.yaml credentials cannot communicate with Tesla API: %s",
                        ex.message,
                    )
                break
    else:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data={CONF_USERNAME: email, CONF_PASSWORD: password},
            )
        )
    return True


async def async_setup_entry(hass, config_entry):
    """Set up Tesla as config entry."""

    if DOMAIN not in hass.data or config_entry.entry_id not in hass.data[DOMAIN]:
        config = config_entry.data
        if DOMAIN not in hass.data:
            hass.data[DOMAIN] = {}
        try:
            websession = aiohttp_client.async_get_clientsession(hass)
            controller = teslaAPI(
                websession, refresh_token=config[CONF_TOKEN], update_interval=300
            )
            (refresh_token, access_token) = await controller.connect()
            _async_save_refresh_token(hass, config_entry, access_token, refresh_token)
            hass.data[DOMAIN][config_entry.entry_id] = {
                "controller": controller,
                "devices": defaultdict(list),
                DATA_LISTENER: list,
            }
            _LOGGER.debug("Connected to the Tesla API.")
        except TeslaException as ex:
            _LOGGER.warning("Unable to communicate with Tesla API: %s", ex.message)
            return False

    all_devices = hass.data[DOMAIN][config_entry.entry_id][
        "controller"
    ].get_homeassistant_components()

    if not all_devices:
        return False

    for device in all_devices:
        hass.data[DOMAIN][config_entry.entry_id]["devices"][device.hass_type].append(
            device
        )

    for component in TESLA_COMPONENTS:
        _LOGGER.debug("Loading %s", component)
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, component)
        )
    return True


async def async_unload_entry(hass, config_entry) -> bool:
    """Unload a config entry."""
    for component in TESLA_COMPONENTS:
        await hass.config_entries.async_forward_entry_unload(config_entry, component)
    if DATA_LISTENER in hass.data[DOMAIN][config_entry.entry_id]:
        for listener in hass.data[DOMAIN][config_entry.entry_id][DATA_LISTENER]:
            listener()
    username = config_entry.title
    hass.data[DOMAIN].pop(config_entry.entry_id)
    _LOGGER.debug("Unloaded entry for %s", username)
    return True


class TeslaDevice(Entity):
    """Representation of a Tesla device."""

    def __init__(self, tesla_device, controller, config_entry=None):
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
    def icon(self):
        """Return the icon of the sensor."""
        return self._icon

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

    async def async_added_to_hass(self):
        """Register state update callback."""
        pass

    async def async_will_remove_from_hass(self):
        """Prepare for unload."""
        pass

    async def async_update(self):
        """Update the state of the device."""
        await self.tesla_device.async_update()

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
        await super().async_added_to_hass()

    async def async_will_remove_from_hass(self):
        """Prepare for unload."""
        await super().async_will_remove_from_hass()

    async def async_update(self):
        """Update the state of the device."""
        if self.config_entry and self.controller.is_token_refreshed():
            (refresh_token, access_token) = self.controller.get_tokens()
            _async_save_refresh_token(
                self.hass, self.config_entry, access_token, refresh_token
            )
            _LOGGER.debug("Saving new tokens in config_entry")
        await self.tesla_device.async_update()
