"""Support for Home Panel sensors."""
from datetime import timedelta
import logging

from homeassistant.components.home_panel import HomePanelDeviceEntity
from homeassistant.components.home_panel.const import (
    DATA_HOME_PANEL_CLIENT,
    DATA_HOST,
    DATA_PASSWORD,
    DATA_PORT,
    DATA_USERNAME,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import HomeAssistantType

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=300)
PARALLEL_UPDATES = 4


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up Home Panel sensor based on a config entry."""
    home_panel_api = hass.data[DOMAIN][DATA_HOME_PANEL_CLIENT]
    host = hass.data[DOMAIN][DATA_HOST]
    port = hass.data[DOMAIN][DATA_PORT]
    username = hass.data[DOMAIN][DATA_USERNAME]
    password = hass.data[DOMAIN][DATA_PASSWORD]

    sensors = [
        HomePanelPageCountSensor(home_panel_api, host, port, username, password),
        HomePanelGroupCountSensor(home_panel_api, host, port, username, password),
        HomePanelCardCountSensor(home_panel_api, host, port, username, password),
    ]

    async_add_entities(sensors, True)


class HomePanelSensor(HomePanelDeviceEntity):
    """Defines a Home Panel sensor."""

    def __init__(
        self,
        home_panel_api,
        host: str,
        port: str,
        username: str,
        password: str,
        name: str,
        icon: str,
        measurement: str,
        unit_of_measurement: str,
    ) -> None:
        """Initialize Home Panel sensor."""
        self._state = None
        self._unit_of_measurement = unit_of_measurement
        self.measurement = measurement
        self.host = host
        self.port = port
        self.username = username

        super().__init__(home_panel_api, username, password, name, icon)

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this sensor."""
        return "_".join(
            [
                DOMAIN,
                self.host,
                str(self.port),
                self.username,
                "sensor",
                self.measurement,
            ]
        )

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit this state is expressed in."""
        return self._unit_of_measurement


class HomePanelPageCountSensor(HomePanelSensor):
    """Defines a Home Panel page count sensor."""

    def __init__(
        self, home_panel_api, host: str, port: str, username: str, password: str
    ):
        """Initialize Home Panel sensor."""
        super().__init__(
            home_panel_api,
            host,
            port,
            username,
            password,
            "Home Panel Pages",
            "mdi:book-open-page-variant",
            "page_count",
            "pages",
        )

    async def _home_panel_update(self) -> bool:
        """Update Home Panel entity."""
        if await self.home_panel_api.async_authenticate(self.username, self.password):
            config = await self.home_panel_api.async_get_config()
            if config and config["pages"]:
                self._state = len(config["pages"])
                return True
        return False


class HomePanelGroupCountSensor(HomePanelSensor):
    """Defines a Home Panel group count sensor."""

    def __init__(
        self, home_panel_api, host: str, port: str, username: str, password: str
    ):
        """Initialize Home Panel sensor."""
        super().__init__(
            home_panel_api,
            host,
            port,
            username,
            password,
            "Home Panel Groups",
            "mdi:select-group",
            "group_count",
            "groups",
        )

    async def _home_panel_update(self) -> bool:
        """Update Home Panel entity."""
        if await self.home_panel_api.async_authenticate(self.username, self.password):
            config = await self.home_panel_api.async_get_config()
            if config and config["groups"]:
                self._state = len(config["groups"])
                return True
        return False


class HomePanelCardCountSensor(HomePanelSensor):
    """Defines a Home Panel card count sensor."""

    def __init__(
        self, home_panel_api, host: str, port: str, username: str, password: str
    ):
        """Initialize Home Panel sensor."""
        super().__init__(
            home_panel_api,
            host,
            port,
            username,
            password,
            "Home Panel Cards",
            "mdi:card-bulleted",
            "card_count",
            "cards",
        )

    async def _home_panel_update(self) -> bool:
        """Update Home Panel entity."""
        if await self.home_panel_api.async_authenticate(self.username, self.password):
            config = await self.home_panel_api.async_get_config()
            if config and config["cards"]:
                self._state = len(config["cards"])
                return True
        return False
