"""Support for retrieving status info from Google Wifi/OnHub routers."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import override

from googlewifiapi import GoogleWifiAPI, GoogleWifiStatus
import probatio

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_MONITORED_CONDITIONS,
    CONF_NAME,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_CURRENT_VERSION,
    ATTR_LAST_RESTART,
    ATTR_LOCAL_IP,
    ATTR_NEW_VERSION,
    ATTR_STATUS,
    ATTR_UPTIME,
    DEFAULT_HOST,
    DEFAULT_NAME,
)
from .coordinator import GoogleWifiCoordinator


@dataclass(frozen=True, kw_only=True)
class GoogleWifiSensorEntityDescription(SensorEntityDescription):
    """Describes GoogleWifi sensor entity."""

    value_fn: Callable[[GoogleWifiStatus], bool | datetime | float | str]


SENSOR_TYPES: tuple[GoogleWifiSensorEntityDescription, ...] = (
    GoogleWifiSensorEntityDescription(
        key=ATTR_CURRENT_VERSION,
        icon="mdi:checkbox-marked-circle-outline",
        value_fn=lambda status: status.software.software_version,
    ),
    GoogleWifiSensorEntityDescription(
        key=ATTR_NEW_VERSION,
        icon="mdi:update",
        value_fn=lambda status: status.software.update_status,
    ),
    # deprecated: The uptime sensor is deprecated and will be removed in 2027.4.0. Use last_restart instead.
    GoogleWifiSensorEntityDescription(
        key=ATTR_UPTIME,
        native_unit_of_measurement=UnitOfTime.DAYS,
        icon="mdi:timelapse",
        value_fn=lambda status: round(status.system.uptime / (3600 * 24), 2),
    ),
    GoogleWifiSensorEntityDescription(
        key=ATTR_LAST_RESTART,
        icon="mdi:restart",
        value_fn=lambda status: status.system.last_restart,
    ),
    GoogleWifiSensorEntityDescription(
        key=ATTR_LOCAL_IP,
        icon="mdi:access-point-network",
        value_fn=lambda status: str(status.wan.local_ip_address),
    ),
    GoogleWifiSensorEntityDescription(
        key=ATTR_STATUS,
        icon="mdi:google",
        value_fn=lambda status: status.wan.online,
    ),
)

SENSOR_KEYS: list[str] = [desc.key for desc in SENSOR_TYPES]

DATA_SCHEMA = probatio.Schema(
    {
        probatio.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
    }
)

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(DATA_SCHEMA).extend(
    {
        probatio.Optional(CONF_MONITORED_CONDITIONS, default=SENSOR_KEYS): probatio.All(
            cv.ensure_list, [probatio.In(SENSOR_KEYS)]
        ),
        probatio.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    _: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Google Wifi sensor."""
    name = config[CONF_NAME]
    host = config[CONF_HOST]
    monitored_conditions = config[CONF_MONITORED_CONDITIONS]

    api = GoogleWifiAPI(host, sess=async_get_clientsession(hass))
    coordinator = GoogleWifiCoordinator(hass, api)
    entities = [
        GoogleWifiSensor(coordinator, name, description)
        for description in SENSOR_TYPES
        if description.key in monitored_conditions
    ]
    add_entities(entities)
    hass.async_create_task(coordinator.async_refresh())


class GoogleWifiSensor(CoordinatorEntity[GoogleWifiCoordinator], SensorEntity):
    """Representation of a Google Wifi sensor."""

    entity_description: GoogleWifiSensorEntityDescription

    def __init__(
        self,
        coordinator: GoogleWifiCoordinator,
        name: str,
        description: GoogleWifiSensorEntityDescription,
    ) -> None:
        """Initialize a Google Wifi sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_name = f"{name}_{description.key}"

    @property
    @override
    def available(self) -> bool:
        """Check if the entity is available."""
        return super().available and self.coordinator.data is not None

    @property
    @override
    def native_value(self) -> bool | datetime | float | str | None:
        """Return the sensor value."""
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)
