"""Support for retrieving status info from Google Wifi/OnHub routers."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import override

from googlewifiapi import GoogleWifiStatus
import probatio

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    CONF_HOST,
    CONF_MONITORED_CONDITIONS,
    CONF_NAME,
    UnitOfTime,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import GoogleWifiConfigEntry
from .const import (
    ATTR_CURRENT_VERSION,
    ATTR_LAST_RESTART,
    ATTR_LOCAL_IP,
    ATTR_NEW_VERSION,
    ATTR_STATUS,
    ATTR_UPTIME,
    DEFAULT_HOST,
    DEFAULT_NAME,
    DOMAIN,
)
from .coordinator import GoogleWifiCoordinator


@dataclass(frozen=True, kw_only=True)
class GoogleWifiSensorEntityDescription(SensorEntityDescription):
    """Describes GoogleWifi sensor entity."""

    value_fn: Callable[[GoogleWifiStatus], bool | datetime | float | str | None]


SENSOR_TYPES: dict[str, GoogleWifiSensorEntityDescription] = {
    ATTR_CURRENT_VERSION: GoogleWifiSensorEntityDescription(
        key=ATTR_CURRENT_VERSION,
        icon="mdi:checkbox-marked-circle-outline",
        value_fn=lambda status: status.software.software_version,
    ),
    ATTR_NEW_VERSION: GoogleWifiSensorEntityDescription(
        key=ATTR_NEW_VERSION,
        icon="mdi:update",
        value_fn=lambda status: (
            "Latest"
            if status.software.update_new_version == "0.0.0.0"
            else status.software.update_new_version
        ),
    ),
    # deprecated: The uptime sensor is deprecated and will be removed in 2027.4.0. Use last_restart instead.
    ATTR_UPTIME: GoogleWifiSensorEntityDescription(
        key=ATTR_UPTIME,
        native_unit_of_measurement=UnitOfTime.DAYS,
        icon="mdi:timelapse",
        value_fn=lambda status: round(status.system.uptime / (3600 * 24), 2),
    ),
    ATTR_LAST_RESTART: GoogleWifiSensorEntityDescription(
        key=ATTR_LAST_RESTART,
        icon="mdi:restart",
        value_fn=lambda status: status.system.last_restart,
    ),
    ATTR_LOCAL_IP: GoogleWifiSensorEntityDescription(
        key=ATTR_LOCAL_IP,
        icon="mdi:access-point-network",
        value_fn=lambda status: (
            str(status.wan.local_ip_address) if status.wan.online else None
        ),
    ),
    ATTR_STATUS: GoogleWifiSensorEntityDescription(
        key=ATTR_STATUS,
        icon="mdi:google",
        value_fn=lambda status: "Online" if status.wan.online else "Offline",
    ),
}

SENSOR_KEYS: list[str] = [desc.key for desc in SENSOR_TYPES.values()]

CONFIG_SCHEMA = probatio.Schema(
    {
        probatio.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
    }
)

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(CONFIG_SCHEMA).extend(
    {
        probatio.Optional(CONF_MONITORED_CONDITIONS, default=SENSOR_KEYS): probatio.All(
            probatio.EnsureList(), [probatio.In(SENSOR_KEYS)]
        ),
        probatio.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


async def async_setup_entry(
    _: HomeAssistant,
    entry: GoogleWifiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Google Wifi sensors."""
    coordinator = entry.runtime_data

    async_add_entities(
        GoogleWifiSensor(coordinator, description)
        for key, description in SENSOR_TYPES.items()
        if key in entry.data.get(CONF_MONITORED_CONDITIONS, SENSOR_KEYS)
        if description.value_fn(coordinator.data) is not None
    )


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    _: AddEntitiesCallback,
    _discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Migrate YAML sensor platform configuration to a config entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=dict(config)
    )
    if result.get("type") is FlowResultType.ABORT:
        return

    ir.async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version="2027.6.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={"domain": DOMAIN, "integration_title": "Google Wifi"},
    )


class GoogleWifiSensor(CoordinatorEntity[GoogleWifiCoordinator], SensorEntity):
    """Representation of a Google Wifi sensor."""

    # pyrefly: ignore[bad-override-mutable-attribute]
    entity_description: GoogleWifiSensorEntityDescription

    def __init__(
        self,
        coordinator: GoogleWifiCoordinator,
        description: GoogleWifiSensorEntityDescription,
    ) -> None:
        """Initialize a Google Wifi sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        data = self.coordinator.data
        if data is None:
            raise RuntimeError("Coordinator data is None, cannot initialize sensor")
        self._attr_name = (
            f"{coordinator.config_entry.title} "
            f"{description.key.replace('_', ' ').title()}"
        )
        self._attr_unique_id = f"{data.system.hardware_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, data.system.hardware_id)},
            name=self.coordinator.config_entry.title,
            manufacturer="Google",
            model_id=data.system.model_id,
            sw_version=data.software.software_version,
        )

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
