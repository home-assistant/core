"""Support for Tesla cars."""
import asyncio
from collections import defaultdict
from datetime import timedelta
import logging

import async_timeout
from teslajsonpy import Controller as TeslaAPI, TeslaException
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    ATTR_BATTERY_CHARGING,
    ATTR_BATTERY_LEVEL,
    CONF_ACCESS_TOKEN,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_TOKEN,
    CONF_USERNAME,
)
from homeassistant.core import callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client, config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import slugify

from .config_flow import (
    CannotConnect,
    InvalidAuth,
    configured_instances,
    validate_input,
)
from .const import (
    CONF_WAKE_ON_START,
    DATA_LISTENER,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_WAKE_ON_START,
    DOMAIN,
    ICONS,
    MIN_SCAN_INTERVAL,
    TESLA_COMPONENTS,
)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                ): vol.All(cv.positive_int, vol.Clamp(min=MIN_SCAN_INTERVAL)),
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
        options = options or {
            CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
            CONF_WAKE_ON_START: DEFAULT_WAKE_ON_START,
        }
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
        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN][email] = {CONF_SCAN_INTERVAL: scan_interval}
    return True


async def async_setup_entry(hass, config_entry):
    """Set up Tesla as config entry."""
    hass.data.setdefault(DOMAIN, {})
    config = config_entry.data
    websession = aiohttp_client.async_get_clientsession(hass)
    email = config_entry.title
    if email in hass.data[DOMAIN] and CONF_SCAN_INTERVAL in hass.data[DOMAIN][email]:
        scan_interval = hass.data[DOMAIN][email][CONF_SCAN_INTERVAL]
        hass.config_entries.async_update_entry(
            config_entry, options={CONF_SCAN_INTERVAL: scan_interval}
        )
        hass.data[DOMAIN].pop(email)
    try:
        controller = TeslaAPI(
            websession,
            refresh_token=config[CONF_TOKEN],
            access_token=config[CONF_ACCESS_TOKEN],
            update_interval=config_entry.options.get(
                CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
            ),
        )
        (refresh_token, access_token) = await controller.connect(
            wake_if_asleep=config_entry.options.get(
                CONF_WAKE_ON_START, DEFAULT_WAKE_ON_START
            )
        )
    except TeslaException as ex:
        _LOGGER.error("Unable to communicate with Tesla API: %s", ex.message)
        return False
    _async_save_tokens(hass, config_entry, access_token, refresh_token)
    coordinator = TeslaDataUpdateCoordinator(
        hass, config_entry=config_entry, controller=controller
    )
    # Fetch initial data so we have data when entities subscribe
    entry_data = hass.data[DOMAIN][config_entry.entry_id] = {
        "coordinator": coordinator,
        "devices": defaultdict(list),
        DATA_LISTENER: [config_entry.add_update_listener(update_listener)],
    }
    _LOGGER.debug("Connected to the Tesla API")

    await coordinator.async_refresh()
    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    all_devices = controller.get_homeassistant_components()

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
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(config_entry, component)
                for component in TESLA_COMPONENTS
            ]
        )
    )
    for listener in hass.data[DOMAIN][config_entry.entry_id][DATA_LISTENER]:
        listener()
    username = config_entry.title
    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)
        _LOGGER.debug("Unloaded entry for %s", username)
        return True
    return False


async def update_listener(hass, config_entry):
    """Update when config_entry options update."""
    controller = hass.data[DOMAIN][config_entry.entry_id]["coordinator"].controller
    old_update_interval = controller.update_interval
    controller.update_interval = config_entry.options.get(CONF_SCAN_INTERVAL)
    if old_update_interval != controller.update_interval:
        _LOGGER.debug(
            "Changing scan_interval from %s to %s",
            old_update_interval,
            controller.update_interval,
        )


class TeslaDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Tesla data."""

    def __init__(self, hass, *, config_entry, controller):
        """Initialize global Tesla data updater."""
        self.controller = controller
        self.config_entry = config_entry

        update_interval = timedelta(seconds=MIN_SCAN_INTERVAL)

        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=update_interval,
        )

    async def _async_update_data(self):
        """Fetch data from API endpoint."""
        if self.controller.is_token_refreshed():
            (refresh_token, access_token) = self.controller.get_tokens()
            _async_save_tokens(
                self.hass, self.config_entry, access_token, refresh_token
            )
            _LOGGER.debug("Saving new tokens in config_entry")

        try:
            # Note: asyncio.TimeoutError and aiohttp.ClientError are already
            # handled by the data update coordinator.
            async with async_timeout.timeout(30):
                return await self.controller.update()
        except TeslaException as err:
            raise UpdateFailed(f"Error communicating with API: {err}")


class TeslaDevice(Entity):
    """Representation of a Tesla device."""

    def __init__(self, tesla_device, coordinator):
        """Initialise the Tesla device."""
        self.tesla_device = tesla_device
        self.coordinator = coordinator
        self._attributes = self.tesla_device.attrs.copy()

    @property
    def name(self):
        """Return the name of the device."""
        return self.tesla_device.name

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return slugify(self.tesla_device.uniq_name)

    @property
    def icon(self):
        """Return the icon of the sensor."""
        if self.device_class:
            return None

        return ICONS.get(self.tesla_device.type)

    @property
    def should_poll(self):
        """No need to poll. Coordinator notifies entity of updates."""
        return False

    @property
    def available(self):
        """Return if entity is available."""
        return self.coordinator.last_update_success

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        attr = self._attributes.copy()
        if self.tesla_device.has_battery():
            attr[ATTR_BATTERY_LEVEL] = self.tesla_device.battery_level()
            attr[ATTR_BATTERY_CHARGING] = self.tesla_device.battery_charging()
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
        self.async_on_remove(self.coordinator.async_add_listener(self.refresh))

    async def async_will_remove_from_hass(self):
        """Prepare for unload."""

    async def async_update(self):
        """Update the state of the device."""
        _LOGGER.debug("Updating state for: %s", self.name)
        await self.coordinator.async_request_refresh()
        self.refresh()

    def refresh(self) -> None:
        """Refresh the state of the device.

        This assumes the coordinator has updated the controller.
        """
        self.tesla_device.refresh()
        self.schedule_update_ha_state()
