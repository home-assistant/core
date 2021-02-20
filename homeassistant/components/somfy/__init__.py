"""Support for Somfy hubs."""
from abc import abstractmethod
import asyncio
from datetime import timedelta
import logging

from pymfy.api.devices.category import Category
import voluptuous as vol

from homeassistant.components.somfy import config_flow
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET, CONF_OPTIMISTIC
from homeassistant.core import callback
from homeassistant.helpers import (
    config_entry_oauth2_flow,
    config_validation as cv,
    device_registry as dr,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from . import api
from .const import API, COORDINATOR, DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=1)
SCAN_INTERVAL_ALL_ASSUMED_STATE = timedelta(minutes=60)

SOMFY_AUTH_CALLBACK_PATH = "/auth/somfy/callback"
SOMFY_AUTH_START = "/auth/somfy"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Inclusive(CONF_CLIENT_ID, "oauth"): cv.string,
                vol.Inclusive(CONF_CLIENT_SECRET, "oauth"): cv.string,
                vol.Optional(CONF_OPTIMISTIC, default=False): cv.boolean,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

SOMFY_COMPONENTS = ["climate", "cover", "sensor", "switch"]


async def async_setup(hass, config):
    """Set up the Somfy component."""
    hass.data[DOMAIN] = {}
    domain_config = config.get(DOMAIN, {})
    hass.data[DOMAIN][CONF_OPTIMISTIC] = domain_config.get(CONF_OPTIMISTIC, False)

    if CONF_CLIENT_ID in domain_config:
        config_flow.SomfyFlowHandler.async_register_implementation(
            hass,
            config_entry_oauth2_flow.LocalOAuth2Implementation(
                hass,
                DOMAIN,
                config[DOMAIN][CONF_CLIENT_ID],
                config[DOMAIN][CONF_CLIENT_SECRET],
                "https://accounts.somfy.com/oauth/oauth/v2/auth",
                "https://accounts.somfy.com/oauth/oauth/v2/token",
            ),
        )

    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry):
    """Set up Somfy from a config entry."""
    # Backwards compat
    if "auth_implementation" not in entry.data:
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, "auth_implementation": DOMAIN}
        )

    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )

    data = hass.data[DOMAIN]
    data[API] = api.ConfigEntrySomfyApi(hass, entry, implementation)

    async def _update_all_devices():
        """Update all the devices."""
        devices = await hass.async_add_executor_job(data[API].get_devices)
        previous_devices = data[COORDINATOR].data
        # Sometimes Somfy returns an empty list.
        if not devices and previous_devices:
            raise UpdateFailed("No devices returned")
        return {dev.id: dev for dev in devices}

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="somfy device update",
        update_method=_update_all_devices,
        update_interval=SCAN_INTERVAL,
    )
    data[COORDINATOR] = coordinator

    await coordinator.async_refresh()

    if all(not bool(device.states) for device in coordinator.data.values()):
        _LOGGER.debug(
            "All devices have assumed state. Update interval has been reduced to: %s",
            SCAN_INTERVAL_ALL_ASSUMED_STATE,
        )
        coordinator.update_interval = SCAN_INTERVAL_ALL_ASSUMED_STATE

    device_registry = await dr.async_get_registry(hass)

    hubs = [
        device
        for device in coordinator.data.values()
        if Category.HUB.value in device.categories
    ]

    for hub in hubs:
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, hub.id)},
            manufacturer="Somfy",
            name=hub.name,
            model=hub.type,
        )

    for component in SOMFY_COMPONENTS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistantType, entry: ConfigEntry):
    """Unload a config entry."""
    hass.data[DOMAIN].pop(API, None)
    await asyncio.gather(
        *[
            hass.config_entries.async_forward_entry_unload(entry, component)
            for component in SOMFY_COMPONENTS
        ]
    )
    return True


class SomfyEntity(CoordinatorEntity, Entity):
    """Representation of a generic Somfy device."""

    def __init__(self, coordinator, device_id, somfy_api):
        """Initialize the Somfy device."""
        super().__init__(coordinator)
        self._id = device_id
        self.api = somfy_api

    @property
    def device(self):
        """Return data for the device id."""
        return self.coordinator.data[self._id]

    @property
    def unique_id(self) -> str:
        """Return the unique id base on the id returned by Somfy."""
        return self._id

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return self.device.name

    @property
    def device_info(self):
        """Return device specific attributes.

        Implemented by platform classes.
        """
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": self.name,
            "model": self.device.type,
            "via_device": (DOMAIN, self.device.parent_id),
            # For the moment, Somfy only returns their own device.
            "manufacturer": "Somfy",
        }

    def has_capability(self, capability: str) -> bool:
        """Test if device has a capability."""
        capabilities = self.device.capabilities
        return bool([c for c in capabilities if c.name == capability])

    def has_state(self, state: str) -> bool:
        """Test if device has a state."""
        states = self.device.states
        return bool([c for c in states if c.name == state])

    @property
    def assumed_state(self) -> bool:
        """Return if the device has an assumed state."""
        return not bool(self.device.states)

    @callback
    def _handle_coordinator_update(self):
        """Process an update from the coordinator."""
        self._create_device()
        super()._handle_coordinator_update()

    @abstractmethod
    def _create_device(self):
        """Update the device with the latest data."""
