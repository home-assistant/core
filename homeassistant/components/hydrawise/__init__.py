"""Support for Hydrawise cloud."""
from dataclasses import dataclass, field
from datetime import timedelta
import logging

from hydrawiser.core import Hydrawiser
from pydrawise import Auth, Controller, Hydrawise as Pydrawise, Zone
from requests.exceptions import ConnectTimeout, HTTPError
import voluptuous as vol

from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect, dispatcher_send
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.event import track_time_interval
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

ALLOWED_WATERING_TIME = [5, 10, 15, 30, 45, 60]

CONF_WATERING_TIME = "watering_minutes"

NOTIFICATION_ID = "hydrawise_notification"
NOTIFICATION_TITLE = "Hydrawise Setup"

DATA_YAML = "yaml"
DOMAIN = "hydrawise"
DEFAULT_WATERING_TIME = 15

PLATFORMS: list[Platform] = [Platform.SWITCH]

SCAN_INTERVAL = timedelta(seconds=30)

SIGNAL_UPDATE_HYDRAWISE = "hydrawise_update"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_ACCESS_TOKEN): cv.string,
                vol.Optional(CONF_SCAN_INTERVAL, default=SCAN_INTERVAL): cv.time_period,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Hunter Hydrawise component."""
    hass.data.setdefault(DOMAIN, {})
    if DOMAIN not in config:
        # We were set up using config flow and not YAML.
        return True

    conf = config[DOMAIN]
    access_token = conf[CONF_ACCESS_TOKEN]
    scan_interval = conf.get(CONF_SCAN_INTERVAL)

    try:
        hydrawise = Hydrawiser(user_token=access_token)
        hass.data[DOMAIN][DATA_YAML] = HydrawiseHub(hydrawise)
    except (ConnectTimeout, HTTPError) as ex:
        _LOGGER.error("Unable to connect to Hydrawise cloud service: %s", str(ex))
        persistent_notification.create(
            hass,
            f"Error: {ex}<br />You will need to restart hass after fixing.",
            title=NOTIFICATION_TITLE,
            notification_id=NOTIFICATION_ID,
        )
        return False

    def hub_refresh(event_time):
        """Call Hydrawise hub to refresh information."""
        _LOGGER.debug("Updating Hydrawise Hub component")
        hass.data[DOMAIN][DATA_YAML].data.update_controller_info()
        dispatcher_send(hass, SIGNAL_UPDATE_HYDRAWISE)

    # Call the Hydrawise API to refresh updates
    track_time_interval(hass, hub_refresh, scan_interval)

    return True


@dataclass
class HydrawiseData:
    """Container for data returned by our DataUpdateCoordinator."""

    controllers: dict[int, Controller] = field(default_factory=dict)
    """Controllers indexed by their id."""

    zones: dict[int, dict[int, Zone]] = field(default_factory=dict)
    """Zones indexed by their controller, then by their id."""


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Hydrawise from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    auth = Auth(entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD])
    api = Pydrawise(auth)

    async def async_update_data() -> HydrawiseData:
        data = HydrawiseData()
        for ctrl in await api.get_controllers():
            data.controllers[ctrl.id] = ctrl
            data.zones[ctrl.id] = {z.id: z for z in await ctrl.get_zones()}
        return data

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=async_update_data,
        update_interval=SCAN_INTERVAL,
    )
    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class HydrawiseHub:
    """Representation of a base Hydrawise device."""

    def __init__(self, data):
        """Initialize the entity."""
        self.data = data


class HydrawiseEntity(Entity):
    """Entity class for Hydrawise devices."""

    _attr_attribution = "Data provided by hydrawise.com"

    def __init__(self, data, description: EntityDescription):
        """Initialize the Hydrawise entity."""
        self.entity_description = description
        self.data = data
        self._attr_name = f"{self.data['name']} {description.name}"

    async def async_added_to_hass(self):
        """Register callbacks."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_UPDATE_HYDRAWISE, self._update_callback
            )
        )

    @callback
    def _update_callback(self):
        """Call update method."""
        self.async_schedule_update_ha_state(True)

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {"identifier": self.data.get("relay")}
