"""Interface to the SmartTub API."""

from datetime import timedelta
import logging

import async_timeout
from smarttub import APIError, LoginFailed, SmartTub

from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, CONF_SCAN_INTERVAL
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, POLLING_TIMEOUT
from .helpers import get_spa_name

_LOGGER = logging.getLogger(__name__)


class SmartTubController:
    """Interface between Home Assistant and the SmartTub API."""

    def __init__(self, hass):
        """Initialize an interface to SmartTub."""
        self._hass = hass
        self._api = SmartTub(async_get_clientsession(hass))
        self._account = None
        self.spas = set()
        self._spa_devices = {}

        self.coordinator = None

    async def async_setup_entry(self, entry):
        """Perform initial setup.

        Authenticate, query static state, set up polling, and otherwise make
        ready for normal operations .
        """

        try:
            await self._api.login(entry.data[CONF_EMAIL], entry.data[CONF_PASSWORD])
        except LoginFailed:
            # credentials were changed or invalidated, we need new ones
            self._hass.async_create_task(
                self._hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": SOURCE_REAUTH},
                    data=None,
                )
            )

            return False

        self._account = await self._api.get_account()

        self.spas = await self._account.get_spas()

        self.coordinator = DataUpdateCoordinator(
            self._hass,
            _LOGGER,
            name=DOMAIN,
            update_method=self.async_update_data,
            update_interval=timedelta(
                seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
        )

        await self.coordinator.async_refresh()

        await self.async_register_devices(entry)

        return True

    async def async_unload_entry(self, entry):
        """Tear down."""
        await self.async_unregister_devices()
        return True

    async def async_update_data(self):
        """Query the API and return the new state."""

        data = {}
        try:
            async with async_timeout.timeout(POLLING_TIMEOUT):
                for spa in self.spas:
                    data[spa.id] = {"status": await spa.get_status()}
        except APIError as err:
            raise UpdateFailed(err) from err

        return data

    async def async_register_devices(self, entry):
        """Register devices with the device registry for all spas."""
        device_registry = await dr.async_get_registry(self._hass)
        for spa in self.spas:
            device = device_registry.async_get_or_create(
                config_entry_id=entry.entry_id,
                connections={(DOMAIN, self._account.id)},
                identifiers={(DOMAIN, spa.id)},
                manufacturer=spa.brand,
                name=get_spa_name(spa),
                model=spa.model,
                # sw_version=config.swversion,
            )
            self._spa_devices[spa.id] = device

    async def async_unregister_devices(self):
        """Unregister all spa devices with the device registry."""
        device_registry = await dr.async_get_registry(self._hass)
        for device in self._spa_devices.values():
            device_registry.async_remove_device(device.id)
        self._spa_devices = {}

    async def get_account_id(self, email, password):
        """Retrieve the account ID corresponding to the specified email and password.

        Returns None if the credentials are invalid.
        """

        api = SmartTub(async_get_clientsession(self._hass))
        try:
            await api.login(email, password)
        except LoginFailed:
            return None
        account = await api.get_account()
        return account.id
