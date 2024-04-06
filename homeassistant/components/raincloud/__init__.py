"""Support for Melnor RainCloud sprinkler water timer."""

from datetime import timedelta
import logging

from raincloudy.core import RainCloudy
from requests.exceptions import ConnectTimeout, HTTPError
import voluptuous as vol

from homeassistant.components import persistent_notification
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    PERCENTAGE,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect, dispatcher_send
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import track_time_interval
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

ALLOWED_WATERING_TIME = [5, 10, 15, 30, 45, 60]

CONF_WATERING_TIME = "watering_minutes"

NOTIFICATION_ID = "raincloud_notification"
NOTIFICATION_TITLE = "Rain Cloud Setup"

DATA_RAINCLOUD = "raincloud"
DOMAIN = "raincloud"
DEFAULT_WATERING_TIME = 15

KEY_MAP = {
    "auto_watering": "Automatic Watering",
    "battery": "Battery",
    "is_watering": "Watering",
    "manual_watering": "Manual Watering",
    "next_cycle": "Next Cycle",
    "rain_delay": "Rain Delay",
    "status": "Status",
    "watering_time": "Remaining Watering Time",
}

ICON_MAP = {
    "auto_watering": "mdi:autorenew",
    "battery": "",
    "is_watering": "",
    "manual_watering": "mdi:water-pump",
    "next_cycle": "mdi:calendar-clock",
    "rain_delay": "mdi:weather-rainy",
    "status": "",
    "watering_time": "mdi:water-pump",
}

UNIT_OF_MEASUREMENT_MAP = {
    "auto_watering": "",
    "battery": PERCENTAGE,
    "is_watering": "",
    "manual_watering": "",
    "next_cycle": "",
    "rain_delay": UnitOfTime.DAYS,
    "status": "",
    "watering_time": UnitOfTime.MINUTES,
}

BINARY_SENSORS = ["is_watering", "status"]

SENSORS = ["battery", "next_cycle", "rain_delay", "watering_time"]

SWITCHES = ["auto_watering", "manual_watering"]

SCAN_INTERVAL = timedelta(seconds=20)

SIGNAL_UPDATE_RAINCLOUD = "raincloud_update"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Optional(CONF_SCAN_INTERVAL, default=SCAN_INTERVAL): cv.time_period,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Melnor RainCloud component."""
    conf = config[DOMAIN]
    username = conf.get(CONF_USERNAME)
    password = conf.get(CONF_PASSWORD)
    scan_interval = conf.get(CONF_SCAN_INTERVAL)

    try:
        raincloud = RainCloudy(username=username, password=password)
        if not raincloud.is_connected:
            raise HTTPError
        hass.data[DATA_RAINCLOUD] = RainCloudHub(raincloud)
    except (ConnectTimeout, HTTPError) as ex:
        _LOGGER.error("Unable to connect to Rain Cloud service: %s", str(ex))
        persistent_notification.create(
            hass,
            f"Error: {ex}<br />You will need to restart hass after fixing.",
            title=NOTIFICATION_TITLE,
            notification_id=NOTIFICATION_ID,
        )
        return False

    def hub_refresh(event_time):
        """Call Raincloud hub to refresh information."""
        _LOGGER.debug("Updating RainCloud Hub component")
        hass.data[DATA_RAINCLOUD].data.update()
        dispatcher_send(hass, SIGNAL_UPDATE_RAINCLOUD)

    # Call the Raincloud API to refresh updates
    track_time_interval(hass, hub_refresh, scan_interval)

    return True


class RainCloudHub:
    """Representation of a base RainCloud device."""

    def __init__(self, data):
        """Initialize the entity."""
        self.data = data


class RainCloudEntity(Entity):
    """Entity class for RainCloud devices."""

    _attr_attribution = "Data provided by Melnor Aquatimer.com"

    def __init__(self, data, sensor_type):
        """Initialize the RainCloud entity."""
        self.data = data
        self._sensor_type = sensor_type
        self._name = f"{self.data.name} {KEY_MAP.get(self._sensor_type)}"
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    async def async_added_to_hass(self):
        """Register callbacks."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_UPDATE_RAINCLOUD, self._update_callback
            )
        )

    def _update_callback(self):
        """Call update method."""
        self.schedule_update_ha_state(True)

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {"identifier": self.data.serial}

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return ICON_MAP.get(self._sensor_type)
