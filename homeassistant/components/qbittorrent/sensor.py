"""Support for monitoring the qBittorrent API."""
from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any, Final

from qbittorrent.client import Client, LoginRequired
from requests.exceptions import RequestException
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import (
    CONF_NAME,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_URL,
    CONF_USERNAME,
    STATE_IDLE,
    UnitOfDataRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType, StateType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

_LOGGER = logging.getLogger(__name__)

DOMAIN = "qBittorrent"

SENSOR_TYPE_CURRENT_STATUS = "current_status"
SENSOR_TYPE_DOWNLOAD_SPEED = "download_speed"
SENSOR_TYPE_UPLOAD_SPEED = "upload_speed"
SENSOR_TYPE_TORRENTS = "torrents"

DEFAULT_NAME = "qBittorrent"
DEFAULT_SCAN_INTERVAL: Final = timedelta(seconds=30)

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key=SENSOR_TYPE_CURRENT_STATUS,
        name="Status",
    ),
    SensorEntityDescription(
        key=SENSOR_TYPE_DOWNLOAD_SPEED,
        name="Down Speed",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.KIBIBYTES_PER_SECOND,
    ),
    SensorEntityDescription(
        key=SENSOR_TYPE_UPLOAD_SPEED,
        name="Up Speed",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.KIBIBYTES_PER_SECOND,
    ),
    SensorEntityDescription(
        key=SENSOR_TYPE_TORRENTS,
        name="Torrents",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement="torrents",
    ),
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_URL): cv.url,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): cv.time_period,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the qBittorrent sensors."""

    try:
        client = Client(config[CONF_URL])
        client.login(config[CONF_USERNAME], config[CONF_PASSWORD])
    except LoginRequired as err:
        _LOGGER.error("Invalid authentication")
        raise PlatformNotReady from err
    except RequestException as err:
        _LOGGER.error("Connection failed")
        raise PlatformNotReady from err

    name = config.get(CONF_NAME)
    scan_interval: timedelta = config.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

    coordinator = QBittorrentUpdateCoordinator(hass, client, scan_interval)

    entities = [
        QBittorrentSensor(description, coordinator, name)
        for description in SENSOR_TYPES
    ]

    add_entities(entities, True)


def format_speed(speed):
    """Return a bytes/s measurement as a human readable string."""
    kb_spd = float(speed) / 1024
    return round(kb_spd, 2 if kb_spd < 0.1 else 1)


class QBittorrentUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the QBittorrent API."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: Client,
        scan_interval: timedelta,
    ) -> None:
        """Initialize."""
        self.client = client

        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=scan_interval)

    def fetch_data(self) -> dict[str, Any]:
        """Fetch data from qBittorrent."""
        try:
            data = self.client.sync_main_data()
            return data
        except RequestException as exception:
            _LOGGER.error("Connection lost")
            raise UpdateFailed() from exception

    async def _async_update_data(self) -> dict[str, Any]:
        """Async update wrapper."""
        return await self.hass.async_add_executor_job(self.fetch_data)


class QBittorrentSensor(CoordinatorEntity[QBittorrentUpdateCoordinator], SensorEntity):
    """Representation of an qBittorrent sensor."""

    def __init__(
        self,
        description: SensorEntityDescription,
        coordinator: QBittorrentUpdateCoordinator,
        client_name,
    ) -> None:
        """Initialize the qBittorrent sensor."""
        super().__init__(coordinator)
        self.entity_description = description

        self._attr_name = f"{client_name} {description.name}"

    @property
    def native_value(self) -> StateType:
        """Return the state."""
        data = self.coordinator.data
        if data is None:
            return None

        download = data["server_state"]["dl_info_speed"]
        upload = data["server_state"]["up_info_speed"]

        sensor_type = self.entity_description.key
        if sensor_type == SENSOR_TYPE_CURRENT_STATUS:
            if upload > 0 and download > 0:
                return "up_down"
            if upload > 0 and download == 0:
                return "seeding"
            if upload == 0 and download > 0:
                return "downloading"
            return STATE_IDLE
        if sensor_type == SENSOR_TYPE_DOWNLOAD_SPEED:
            return format_speed(download)
        if sensor_type == SENSOR_TYPE_UPLOAD_SPEED:
            return format_speed(upload)
        if sensor_type == SENSOR_TYPE_TORRENTS:
            return len(data["torrents"])
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        attrs = {}
        if self.entity_description.key == SENSOR_TYPE_TORRENTS:
            if self.coordinator.data is not None:
                torrents = self.coordinator.data["torrents"]
                # pylint: disable=consider-using-tuple
                attrs["Torrents"] = [
                    {k: entry[k] for k in ["name", "eta", "progress", "state"]}
                    for entry in torrents.values()
                ]
                current_time = datetime.now().replace(microsecond=0)
                for entry in attrs["Torrents"]:
                    entry["eta"] = current_time + timedelta(seconds=entry["eta"])
        return attrs
