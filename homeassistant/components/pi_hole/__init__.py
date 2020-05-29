"""The pi_hole component."""
import asyncio
from datetime import timedelta
import logging
from typing import Any, Dict

from hole import Hole
from hole.exceptions import HoleError
import voluptuous as vol

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_NAME,
    CONF_SSL,
    CONF_VERIFY_SSL,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_DISABLE_SECONDS,
    CONF_LOCATION,
    DEFAULT_DISABLE_SECONDS,
    DEFAULT_LOCATION,
    DEFAULT_NAME,
    DEFAULT_SSL,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    SERVICE_DISABLE,
    SERVICE_DISABLE_ATTR_DURATION,
    SERVICE_DISABLE_ATTR_NAME,
    SERVICE_ENABLE,
    SERVICE_ENABLE_ATTR_NAME,
)

LOGGER = logging.getLogger(__name__)

PI_HOLE_SCHEMA = vol.Schema(
    vol.All(
        {
            vol.Required(CONF_HOST): cv.string,
            vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
            vol.Optional(CONF_API_KEY): cv.string,
            vol.Optional(
                CONF_DISABLE_SECONDS, default=DEFAULT_DISABLE_SECONDS
            ): cv.positive_int,
            vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
            vol.Optional(CONF_LOCATION, default=DEFAULT_LOCATION): cv.string,
            vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
        },
    )
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema(vol.All(cv.ensure_list, [PI_HOLE_SCHEMA]))},
    extra=vol.ALLOW_EXTRA,
)

SERVICE_DISABLE_SCHEMA = vol.Schema(
    vol.All(
        {
            vol.Required(SERVICE_DISABLE_ATTR_DURATION): vol.All(
                cv.time_period_str, cv.positive_timedelta
            ),
            vol.Optional(SERVICE_DISABLE_ATTR_NAME): str,
        },
    )
)

SERVICE_ENABLE_SCHEMA = vol.Schema({vol.Optional(SERVICE_ENABLE_ATTR_NAME): str})


PLATFORM_DOMAINS = [SENSOR_DOMAIN, BINARY_SENSOR_DOMAIN, SWITCH_DOMAIN]
SCAN_INTERVAL = timedelta(seconds=20)


async def async_setup(hass: HomeAssistantType, config: Dict) -> bool:
    """Set up the pi_hole integration."""

    hass.data.setdefault(DOMAIN, {})

    # import
    if DOMAIN in config:
        for conf in config[DOMAIN]:
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN, context={"source": SOURCE_IMPORT}, data=conf
                )
            )

    # TODO: Service stuff below

    # TODO: Check this? May need to refactor where we get API client
    def get_pi_hole_from_name(name):
        pi_hole = hass.data[DOMAIN].get(name)
        if pi_hole is None:
            LOGGER.error("Unknown Pi-hole name %s", name)
            return None
        if not pi_hole.api.api_token:
            LOGGER.error(
                "Pi-hole %s must have an api_key provided in configuration to be enabled",
                name,
            )
            return None
        return pi_hole

    async def disable_service_handler(call):
        """Handle the service call to disable a single Pi-Hole or all configured Pi-Holes."""
        duration = call.data[SERVICE_DISABLE_ATTR_DURATION].total_seconds()
        name = call.data.get(SERVICE_DISABLE_ATTR_NAME)

        async def do_disable(name):
            """Disable the named Pi-Hole."""
            pi_hole = get_pi_hole_from_name(name)
            if pi_hole is None:
                return

            LOGGER.debug(
                "Disabling Pi-hole '%s' (%s) for %d seconds",
                name,
                pi_hole.api.host,
                duration,
            )
            await pi_hole.api.disable(duration)

        if name is not None:
            await do_disable(name)
        else:
            for name in hass.data[DOMAIN]:
                await do_disable(name)

    async def enable_service_handler(call):
        """Handle the service call to enable a single Pi-Hole or all configured Pi-Holes."""

        name = call.data.get(SERVICE_ENABLE_ATTR_NAME)

        async def do_enable(name):
            """Enable the named Pi-Hole."""
            pi_hole = get_pi_hole_from_name(name)
            if pi_hole is None:
                return

            LOGGER.debug("Enabling Pi-hole '%s' (%s)", name, pi_hole.api.host)
            await pi_hole.api.enable()

        if name is not None:
            await do_enable(name)
        else:
            for name in hass.data[DOMAIN]:
                await do_enable(name)

    hass.services.async_register(
        DOMAIN, SERVICE_DISABLE, disable_service_handler, schema=SERVICE_DISABLE_SCHEMA
    )

    hass.services.async_register(
        DOMAIN, SERVICE_ENABLE, enable_service_handler, schema=SERVICE_ENABLE_SCHEMA
    )

    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry) -> bool:
    """Set up Pi-hole entry."""
    name = entry.data[CONF_NAME]
    host = entry.data[CONF_HOST]
    use_tls = entry.data[CONF_SSL]
    verify_tls = entry.data[CONF_VERIFY_SSL]
    location = entry.data[CONF_LOCATION]
    api_key = entry.data.get(CONF_API_KEY)
    disable_seconds = entry.data.get(CONF_DISABLE_SECONDS)

    LOGGER.debug("Setting up %s integration with host %s", DOMAIN, host)

    session = async_get_clientsession(hass, verify_tls)
    coordinator = PiHoleDataUpdateCoordinator(
        hass,
        Hole(
            host, hass.loop, session, location=location, tls=use_tls, api_token=api_key,
        ),
        name,
        disable_seconds,
    )
    await coordinator.async_refresh()
    LOGGER.debug("Finished refreshing from %s, %s", host, name)

    hass.data[DOMAIN][entry.entry_id] = coordinator

    for domain in PLATFORM_DOMAINS:
        # Switch domain requires an api_key
        if api_key or domain != SWITCH_DOMAIN:
            hass.async_create_task(
                hass.config_entries.async_forward_entry_setup(entry, domain)
            )

    return True


async def async_unload_entry(hass, entry):
    """Unload pi-hole entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, domain)
                for domain in PLATFORM_DOMAINS
            ]
        )
    )

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class PiHoleDataUpdateCoordinator(DataUpdateCoordinator):
    """Get the latest data and update the states."""

    def __init__(
        self, hass: HomeAssistantType, hole: Hole, name: str, disable_seconds: int
    ):
        """Initialize the data object."""
        self.api = hole
        self.disable_seconds = disable_seconds
        self.available = False

        super().__init__(
            hass, LOGGER, name=f"{name}", update_interval=SCAN_INTERVAL,
        )

    @property
    def unique_id(self) -> str:
        """Return unique id for the device."""
        return f"{self.api.host}_{self.name}"

    async def _async_update_data(self) -> Dict:
        """Get the latest data from the Pi-hole."""

        try:
            await self.api.get_data()
            data = self.api.data
            self.available = True
            LOGGER.debug("We got data from the client for %s", self.name)
            # TODO: Decide if we should raise an exception here if we have no data
            return data
        except HoleError as error:
            self.available = False
            raise UpdateFailed(f"Error retrieving data form Pi-Hole: {error}")


class PiHoleEntity(Entity):
    """Defines a base Pi-Hole entity."""

    def __init__(
        self, *, device_id: str, name: str, coordinator: PiHoleDataUpdateCoordinator
    ):
        """Initialize the Pi-Hole entity."""
        self._device_id = device_id
        self._name = name
        self.coordinator = coordinator

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.available

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def should_poll(self) -> bool:
        """Return the polling requirement of the entity."""
        return False

    @property
    def device_state_attributes(self):
        """Return the state attributes of the Pi-Hole."""
        return self.coordinator.data

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information about this Pi-Hole device."""
        if self._device_id is None:
            return None

        return {
            "identifiers": {(DOMAIN, self._device_id)},
            "name": self._name,
            "manufacturer": "Pi-hole",
        }

    async def async_added_to_hass(self) -> None:
        """Connect to dispatcher listening for entity data notifications."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_update(self) -> None:
        """Update a Pi-Hole entity."""
        await self.coordinator.async_request_refresh()
