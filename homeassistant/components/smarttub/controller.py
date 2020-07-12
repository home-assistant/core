"""Interface to the SmartTub API."""

from collections import defaultdict
from datetime import timedelta
import logging

from smarttub import APIError, LoginFailed, SmartTub

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, CONF_SCAN_INTERVAL
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class SmartTubController:
    """Interface between Home Assistant and the SmartTub API."""

    def __init__(self, hass):
        """Initialize an interface to SmartTub."""
        self._hass = hass
        self._api = SmartTub(async_get_clientsession(hass))
        self._account = None
        self._spas = {}
        self._stop_polling = None

        self._coordinator = None
        self.spa_ids = set()

    async def async_setup(self, entry):
        """Perform initial setup.

        Authenticate, query static state, set up polling, and otherwise make
        ready for normal operations .
        """

        await self._api.login(entry.data[CONF_EMAIL], entry.data[CONF_PASSWORD])

        self._account = await self._api.get_account()

        self._spas = {spa.id: spa for spa in await self._account.get_spas()}
        self.spa_ids = set(self._spas)

        self._coordinator = DataUpdateCoordinator(
            self._hass,
            _LOGGER,
            name=DOMAIN,
            update_method=self.async_update_data,
            update_interval=timedelta(
                seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
        )

        await self._coordinator.async_refresh()

        device_registry = await dr.async_get_registry(self._hass)
        for spa in self._spas.values():
            device_registry.async_get_or_create(
                config_entry_id=entry.entry_id,
                connections={(DOMAIN, self._account.id)},
                identifiers={(DOMAIN, spa.id)},
                manufacturer=spa.brand,
                name=self.get_spa_name(spa.id),
                model=spa.model,
                # sw_version=config.swversion,
            )

        return True

    async def async_update_data(self):
        """Query the API and update our copy of the state."""

        data = defaultdict(dict)
        try:
            for spa_id, spa in self._spas.items():
                data[spa_id]["status"] = await spa.get_status()
        except APIError as err:
            raise UpdateFailed(err)

        return data

    async def async_register_entity(self, entity):
        """Register a new entity to receive updates."""
        entity.async_on_remove(
            self._coordinator.async_add_listener(entity.async_write_ha_state)
        )

    async def async_update_entity(self, entity):
        """Request a state update on behalf of entity."""
        self._coordinator.async_request_refresh()

    async def validate_credentials(self, email, password):
        """Check if the specified credentials are valid for authenticating to SmartTub."""
        api = SmartTub(async_get_clientsession(self._hass))
        try:
            await api.login(email, password)
        except LoginFailed:
            return False
        return True

    def entity_is_available(self, entity):
        """Indicate whether the entity has state available."""
        return self._coordinator.last_update_success

    def get_spa_name(self, spa_id):
        """Retrieve the name of the specified spa."""
        spa = self._spas[spa_id]
        return f"{spa.brand} {spa.model}"

    def _get_status_value(self, spa_id, path):
        """Retrieve a value from the data returned by Spa.get_status().

        Nested keys can be specified by a dotted path, e.g.
        status[foo][bar] is 'foo.bar'.
        """

        status = self._coordinator.data[spa_id].get("status")
        if status is None:
            return None

        for key in path.split("."):
            status = status[key]

        return status

    def get_target_water_temperature(self, spa_id) -> float:
        """Return the target water temperature."""
        return self._get_status_value(spa_id, "setTemperature")

    def get_current_water_temperature(self, spa_id) -> float:
        """Return the current water temperature."""
        return self._get_status_value(spa_id, "water.temperature")

    def get_heater_status(self, spa_id) -> str:
        """Return the status of the heater (e.g. 'OFF')."""
        return self._get_status_value(spa_id, "heater")
