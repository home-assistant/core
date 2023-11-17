"""Support for Krisinformation sensor."""
from datetime import timedelta
import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import Throttle

from .const import CONF_COUNTY, DEFAULT_NAME
from .crisis_alerter import CrisisAlerter, Error

_LOGGER = logging.getLogger(__name__)
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=120)


async def async_setup_entry(
    hass: HomeAssistant,
    config: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the departure sensor."""
    name = config.data.get(CONF_NAME, DEFAULT_NAME)
    county = config.data[CONF_COUNTY]

    crisis_alerter = CrisisAlerter(county)

    sensor = CrisisAlerterSensor(config.entry_id, name, crisis_alerter)

    async_add_entities([sensor], False)


class CrisisAlerterSensor(SensorEntity):
    """Implementation of Krisinformations crisis alerter sensor."""

    _attr_attribution = "Alerts provided by Krisinformation"
    _attr_icon = "mdi:alert"

    def __init__(
        self, unique_id: str, name: str, crisis_alerter: CrisisAlerter
    ) -> None:
        """Initialize the sensor."""
        self._attr_unique_id = unique_id
        self._attr_name = name
        self._crisis_alerter = crisis_alerter
        self._state: str | None = None
        self._web: str | None = None
        self._published: str | None = None
        self._area: str | None = None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return {
            "Länk": self._web,
            "Publicerad": self._published,
            "Område": self._area,
        }

    def added_to_hass(self) -> None:
        """Handle when entity is added."""
        if self.hass.state != CoreState.running:
            self.hass.bus.listen_once(EVENT_HOMEASSISTANT_STARTED, self.first_update)
        else:
            self.first_update()

    @property
    def name(self) -> str | None:
        """Return the name of the sensor."""
        return self._attr_name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def first_update(self, _=None) -> None:
        """Run first update and write state."""
        self.update()
        self.async_write_ha_state()

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
