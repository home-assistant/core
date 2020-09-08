"""The Omnilogic integration."""
import asyncio
from datetime import timedelta
import logging

from omnilogic import LoginException, OmniLogic, OmniLogicException

from homeassistant.components.sensor import ENTITY_ID_FORMAT
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, PlatformNotReady
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    COORDINATOR,
    DOMAIN,
    OMNI_API,
    POLL_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Omnilogic component."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Omnilogic from a config entry."""

    conf = entry.data
    username = conf[CONF_USERNAME]
    password = conf[CONF_PASSWORD]
    polling_interval = conf[POLL_INTERVAL]
    api = OmniLogic(username, password)

    try:
        await api.connect()
        await api.get_telemetry_data()
    except LoginException as e:
        _LOGGER.debug(f"OmniLogic login error: {e}")
        raise PlatformNotReady
    except OmniLogicException as e:
        _LOGGER.debug(f"OmniLogic API error: {e}")

    coordinator = OmniLogicUpdateCoordinator(
        hass=hass,
        api=api,
        name="Omnilogic",
        polling_interval=polling_interval,
    )
    await coordinator.async_refresh()

    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        COORDINATOR: coordinator,
        OMNI_API: api,
    }

    for component in PLATFORMS:
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
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class OmniLogicUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching update data from single endpoint."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: str,
        name: str,
        polling_interval: int,
    ):
        """Initialize the global Omnilogic data updater."""
        self.api = api

        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=name,
            update_interval=timedelta(seconds=polling_interval),
        )

    def update_listeners(self):
        """Call update on all listeners."""
        for update_callback in self._listeners:
            update_callback()

    async def _async_update_data(self):
        """Fetch data from OmniLogic."""
        try:
            _LOGGER.debug("Updating the coordinator data.")
            data = await self.api.get_telemetry_data()
            return data

        except OmniLogicException as error:
            raise UpdateFailed(f"Error updating from OmniLogic: {error}") from error


class OmniLogicEntity(CoordinatorEntity):
    """Defines the base OmniLogic entity."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        kind: str,
        name: str,
        backyard: dict,
        bow: dict,
        icon: str,
        sensordata: dict,
    ):
        """Initialize the OmniLogic Entity."""
        super().__init__(coordinator)

        if bow != {}:
            sensorname = (
                backyard["BackyardName"].replace(" ", "_")
                + "_"
                + bow["Name"].replace(" ", "_")
                + "_"
                + kind
            )
        else:
            sensorname = backyard["BackyardName"].replace(" ", "_") + "_" + kind

        self._kind = kind
        self._name = None
        self.entity_id = ENTITY_ID_FORMAT.format(sensorname)
        self._unique_id = ENTITY_ID_FORMAT.format(sensorname)
        self._backyard = backyard
        self._backyard_name = backyard["BackyardName"]
        self._state = None
        self._icon = icon
        self._bow = bow
        self.coordinator = coordinator
        self.bow = bow
        self.sensordata = sensordata
        self._attrs = {"MspSystemId": backyard["systemId"]}
        self.alarms = []
        self._unsub_dispatcher = None

    @property
    def unique_id(self) -> str:
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return self._unique_id

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def icon(self):
        """Return the icon for the entity."""
        return self._icon

    @property
    def device_state_attributes(self):
        """Return the attributes."""
        return self._attrs

    @property
    def device_info(self):
        """Define the device as back yard/MSP System."""

        return {
            ATTR_IDENTIFIERS: {(DOMAIN, self._attrs["MspSystemId"])},
            ATTR_NAME: self._backyard.get("BackyardName"),
            ATTR_MANUFACTURER: "Hayward",
            ATTR_MODEL: "OmniLogic",
        }

    async def async_update(self):
        """Update Omnilogic entity."""
        await self.coordinator.async_request_refresh()

    async def async_added_to_hass(self):
        """Subscribe to updates."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )
