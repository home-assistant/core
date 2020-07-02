"""The Elexa Guardian integration."""
import asyncio
from datetime import timedelta

from aioguardian import Client
from aioguardian.errors import GuardianError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION, CONF_IP_ADDRESS, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    API_SYSTEM_DIAGNOSTICS,
    API_SYSTEM_ONBOARD_SENSOR_STATUS,
    API_VALVE_STATUS,
    API_WIFI_STATUS,
    CONF_UID,
    DATA_COORDINATOR,
    DOMAIN,
    LOGGER,
)

DEFAULT_UPDATE_INTERVAL = timedelta(seconds=30)

PLATFORMS = ["binary_sensor", "sensor", "switch"]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Elexa Guardian component."""
    hass.data[DOMAIN] = {DATA_COORDINATOR: {}}
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Elexa Guardian from a config entry."""
    guardian = Guardian(hass, entry)
    await guardian.async_refresh()
    hass.data[DOMAIN][DATA_COORDINATOR][entry.entry_id] = guardian

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN][DATA_COORDINATOR].pop(entry.entry_id)

    return unload_ok


class Guardian(DataUpdateCoordinator):
    """Define a class to communicate with a Guardian valve controller.

    Normally, we'd use a single DataUpdateCoordinator class for each API call; however,
    because the valve controller's API-over-UDP cannot handle concurrent connections
    easily, we extend a single DataUpdateCoordinator with the needed functionality.
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize."""
        super().__init__(
            hass,
            LOGGER,
            name=entry.data[CONF_UID],
            update_interval=DEFAULT_UPDATE_INTERVAL,
            update_method=self.async_update,
        )

        self._hass = hass
        self.client = Client(entry.data[CONF_IP_ADDRESS], port=entry.data[CONF_PORT])
        self.uid = entry.data[CONF_UID]

        self._api_init_lock = asyncio.Lock()
        self._api_interest_count = {
            API_SYSTEM_ONBOARD_SENSOR_STATUS: 0,
            API_VALVE_STATUS: 0,
            API_WIFI_STATUS: 0,
        }
        self._api_optional_coros = {
            API_SYSTEM_ONBOARD_SENSOR_STATUS: self.client.system.onboard_sensor_status,
            API_VALVE_STATUS: self.client.valve.status,
            API_WIFI_STATUS: self.client.wifi.status,
        }

    @callback
    def async_deregister_api_interest(self, api: str) -> None:
        """Decrement interest in an API category."""
        if self._api_interest_count[api] == 0:
            return

        self._api_interest_count[api] -= 1

    async def async_register_api_interest(self, api: str) -> None:
        """Increment interest in an API category."""
        self._api_interest_count[api] += 1

        # If an entity registers interest in a particular API category and the data
        # doesn't exist for it yet, make the API call and grab the data:
        async with self._api_init_lock, self.client:
            if api in self.data:
                return

            try:
                resp = await self._api_optional_coros[api]()
            except GuardianError as err:
                LOGGER.error(
                    "Error fetching %s data: initial %s returned %s",
                    self.name,
                    api,
                    err,
                )
                self.data[api] = {}
                return

            self.data[api] = resp["data"]

    async def async_update(self) -> dict:
        """Get updated data from the valve controller."""
        data = {}

        async with self.client:
            # Diagnostics info will be relevant no matter which entities are active:
            tasks = {API_SYSTEM_DIAGNOSTICS: self.client.system.diagnostics()}

            # If at least one entity has registered interest in an API call, include it
            # in the update:
            for api in self._api_interest_count:
                if self._api_interest_count[api] == 0:
                    continue
                tasks[api] = self._api_optional_coros[api]()

            results = await asyncio.gather(*tasks.values(), return_exceptions=True)

        for api, result in zip(tasks, results):
            if isinstance(result, GuardianError):
                LOGGER.error("Error fetching %s data: %s", self.name, result)
            data[api] = result["data"]

        return data


class GuardianEntity(Entity):
    """Define a base Guardian entity."""

    def __init__(
        self, guardian: Guardian, kind: str, name: str, device_class: str, icon: str
    ):
        """Initialize."""
        self._attrs = {ATTR_ATTRIBUTION: "Data provided by Elexa"}
        self._available = True
        self._device_class = device_class
        self._guardian = guardian
        self._icon = icon
        self._kind = kind
        self._name = name

    @property
    def available(self):
        """Return whether the entity is available."""
        return bool(self._guardian.data[API_SYSTEM_DIAGNOSTICS])

    @property
    def device_class(self):
        """Return the device class."""
        return self._device_class

    @property
    def device_info(self):
        """Return device registry information for this entity."""
        return {
            "identifiers": {(DOMAIN, self._guardian.uid)},
            "manufacturer": "Elexa",
            "model": self._guardian.data[API_SYSTEM_DIAGNOSTICS]["firmware"],
            "name": f"Guardian {self._guardian.uid}",
        }

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attrs

    @property
    def icon(self) -> str:
        """Return the icon."""
        return self._icon

    @property
    def name(self):
        """Return the name of the entity."""
        return f"Guardian {self._guardian.uid}: {self._name}"

    @property
    def should_poll(self) -> bool:
        """Return True if entity has to be polled for state."""
        return False

    @property
    def unique_id(self):
        """Return the unique ID of the entity."""
        return f"{self._guardian.uid}_{self._kind}"

    @callback
    def _async_internal_added_to_hass(self):
        """Perform tasks when the entity is added."""
        self.async_on_remove(self._guardian.async_add_listener(self._update_callback))
        self._async_update_from_latest_data()

    @callback
    def _async_update_from_latest_data(self):
        """Update the entity."""
        raise NotImplementedError

    @callback
    def _update_callback(self):
        """Define a callback to update the entity's state from the latest data."""
        self._async_update_from_latest_data()
        self.async_write_ha_state()
