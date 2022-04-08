"""Support for Hydrawise cloud."""
from datetime import timedelta
import logging

from hydrawiser.core import Hydrawiser
from requests.exceptions import ConnectTimeout, HTTPError
import voluptuous as vol

from homeassistant.components import persistent_notification
from homeassistant.const import ATTR_ATTRIBUTION, CONF_ACCESS_TOKEN, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect, dispatcher_send
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.event import track_time_interval
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

ALLOWED_WATERING_TIME = [5, 10, 15, 30, 45, 60]

ATTRIBUTION = "Data provided by hydrawise.com"

CONF_WATERING_TIME = "watering_minutes"

NOTIFICATION_ID = "hydrawise_notification"
NOTIFICATION_TITLE = "Hydrawise Setup"

DATA_HYDRAWISE = "hydrawise"
DOMAIN = "hydrawise"
DEFAULT_WATERING_TIME = 15

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
    conf = config[DOMAIN]
    access_token = conf[CONF_ACCESS_TOKEN]
    scan_interval = conf.get(CONF_SCAN_INTERVAL)

    try:
        hydrawise = Hydrawiser(user_token=access_token)
        hass.data[DATA_HYDRAWISE] = HydrawiseHub(hydrawise)
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
        hass.data[DATA_HYDRAWISE].data.update_controller_info()
        dispatcher_send(hass, SIGNAL_UPDATE_HYDRAWISE)

    # Call the Hydrawise API to refresh updates
    track_time_interval(hass, hub_refresh, scan_interval)

    return True


class HydrawiseHub:
    """Representation of a base Hydrawise device."""

    def __init__(self, data):
        """Initialize the entity."""
        self.data = data


class HydrawiseEntity(Entity):
    """Entity class for Hydrawise devices."""

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
        return {ATTR_ATTRIBUTION: ATTRIBUTION, "identifier": self.data.get("relay")}
