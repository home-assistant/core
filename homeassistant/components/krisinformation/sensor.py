"""Support for Krisinformation sensor."""
from datetime import timedelta
import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import Throttle

from .const import DEFAULT_NAME
from .crisis_alerter import CrisisAlerter, Error

_LOGGER = logging.getLogger(__name__)
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=120)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the departure sensor."""
    name = config.get(CONF_NAME, DEFAULT_NAME)
    crisis_alerter = CrisisAlerter()
    sensors = [CrisisAlerterSensor(crisis_alerter, name)]

    add_entities(sensors, True)


class CrisisAlerterSensor(SensorEntity):
    """Implementation of Krisinformations crisis alerter sensor."""

    _attr_attribution = "Alerts provided by Krisinformation"
    _attr_icon = "mdi:alert"

    def __init__(self, crisis_alerter: CrisisAlerter, name: str) -> None:
        """Initialize the sensor."""
        self._crisis_alerter = crisis_alerter
        self._name = name
        self._state: str | None = None
        self._web: str | None = None
        self._published: str | None = None
        self._area: str | None = None

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {
            "Länk": self._web,
            "Publicerad": self._published,
            "Område": self._area,
        }

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self) -> None:
        """Get the latest alerts."""
        try:
            response = self._crisis_alerter.news()
            if len(response) > 0:
                news = response[0]
                self._state = news["PushMessage"]
                self._web = news["Web"]
                self._published = news["Published"]
                self._area = (
                    news["Area"][0]["Description"] if len(news["Area"]) > 0 else None
                )
            else:
                self._state = "Inga larm"
        except Error as error:
            _LOGGER.error("Error fetching data: %s", error)
            self._state = "Unavailable"
