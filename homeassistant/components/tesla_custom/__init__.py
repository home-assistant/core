"""Support for Tesla cars."""
import asyncio
from collections import defaultdict
from datetime import timedelta
import logging

import async_timeout
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_TOKEN,
    CONF_USERNAME,
    HTTP_UNAUTHORIZED,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from teslajsonpy import Controller as TeslaAPI
from teslajsonpy.exceptions import IncompleteCredentials, TeslaException

from .config_flow import CannotConnect, InvalidAuth, validate_input
from .const import (
    CONF_EXPIRATION,
    CONF_WAKE_ON_START,
    DATA_LISTENER,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_WAKE_ON_START,
    DOMAIN,
    MIN_SCAN_INTERVAL,
    PLATFORMS,
)

_LOGGER = logging.getLogger(__name__)


@callback
def _async_save_tokens(hass, config_entry, access_token, refresh_token, expiration):
    hass.config_entries.async_update_entry(
        config_entry,
        data={
            **config_entry.data,
            CONF_ACCESS_TOKEN: access_token,
            CONF_TOKEN: refresh_token,
            CONF_EXPIRATION: expiration,
        },
    )


@callback
def _async_configured_emails(hass):
    """Return a set of configured Tesla emails."""
    return {entry.title for entry in hass.config_entries.async_entries(DOMAIN)}


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
    if email in _async_configured_emails(hass):
        try:
            info = await validate_input(hass, config)
        except (CannotConnect, InvalidAuth):
            return False
        _update_entry(
            email,
            data={
                CONF_ACCESS_TOKEN: info[CONF_ACCESS_TOKEN],
                CONF_TOKEN: info[CONF_TOKEN],
                CONF_EXPIRATION: info[CONF_EXPIRATION],
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
    # pylint: disable=too-many-locals
    """Set up Tesla as config entry."""
    hass.data.setdefault(DOMAIN, {})
    config = config_entry.data
    email = config_entry.title
    if email in hass.data[DOMAIN] and CONF_SCAN_INTERVAL in hass.data[DOMAIN][email]:
        scan_interval = hass.data[DOMAIN][email][CONF_SCAN_INTERVAL]
        hass.config_entries.async_update_entry(
            config_entry, options={CONF_SCAN_INTERVAL: scan_interval}
        )
        hass.data[DOMAIN].pop(email)
    try:
        controller = TeslaAPI(
            websession=None,
            email=config.get(CONF_USERNAME),
            password=config.get(CONF_PASSWORD),
            refresh_token=config[CONF_TOKEN],
            access_token=config[CONF_ACCESS_TOKEN],
            expiration=config.get(CONF_EXPIRATION, 0),
            update_interval=config_entry.options.get(
                CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
            ),
        )
        result = await controller.connect(
            wake_if_asleep=config_entry.options.get(
                CONF_WAKE_ON_START, DEFAULT_WAKE_ON_START
            )
        )
        refresh_token = result["refresh_token"]
        access_token = result["access_token"]
        expiration = result["expiration"]
    except IncompleteCredentials:
        _async_start_reauth(hass, config_entry)
        return False
    except TeslaException as ex:
        if ex.code == HTTP_UNAUTHORIZED:
            _async_start_reauth(hass, config_entry)
        _LOGGER.error("Unable to communicate with Tesla API: %s", ex.message)
        return False
    _async_save_tokens(hass, config_entry, access_token, refresh_token, expiration)
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

    await coordinator.async_config_entry_first_refresh()

    all_devices = controller.get_homeassistant_components()

    if not all_devices:
        return False

    for device in all_devices:
        entry_data["devices"][device.hass_type].append(device)

    for platform in PLATFORMS:
        _LOGGER.debug("Loading %s", platform)
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, platform)
        )
    return True


async def async_unload_entry(hass, config_entry) -> bool:
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(config_entry, platform)
                for platform in PLATFORMS
            ]
        )
    )
    await hass.data[DOMAIN].get(config_entry.entry_id)[
        "coordinator"
    ].controller.disconnect()
    for listener in hass.data[DOMAIN][config_entry.entry_id][DATA_LISTENER]:
        listener()
    username = config_entry.title
    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)
        _LOGGER.debug("Unloaded entry for %s", username)
        return True
    return False


def _async_start_reauth(hass: HomeAssistant, entry: ConfigEntry):
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "reauth"},
            data=entry.data,
        )
    )
    _LOGGER.error("Credentials are no longer valid. Please reauthenticate")


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
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
        )

    async def _async_update_data(self):
        """Fetch data from API endpoint."""
        if self.controller.is_token_refreshed():
            result = self.controller.get_tokens()
            refresh_token = result["refresh_token"]
            access_token = result["access_token"]
            expiration = result["expiration"]
            _async_save_tokens(
                self.hass, self.config_entry, access_token, refresh_token, expiration
            )
            _LOGGER.debug("Saving new tokens in config_entry")

        try:
            # Note: asyncio.TimeoutError and aiohttp.ClientError are already
            # handled by the data update coordinator.
            async with async_timeout.timeout(30):
                return await self.controller.update()
        except IncompleteCredentials:
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
        except TeslaException as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
