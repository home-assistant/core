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
from .coordinator import GoogleWifiConfigEntry, GoogleWifiCoordinator

INTEGRATION_TITLE = "Google Wifi"
_IMPORT_FAILURE_REASONS = {"cannot_connect", "invalid_response", "unknown"}


@dataclass(frozen=True, kw_only=True)
class GoogleWifiSensorEntityDescription(SensorEntityDescription):
    """Describes GoogleWifi sensor entity."""

    value_fn: Callable[[GoogleWifiStatus], bool | datetime | float | str | None]


SENSOR_TYPES: tuple[GoogleWifiSensorEntityDescription, ...] = (
    GoogleWifiSensorEntityDescription(
        key=ATTR_CURRENT_VERSION,
        translation_key=ATTR_CURRENT_VERSION,
        icon="mdi:checkbox-marked-circle-outline",
        value_fn=lambda status: status.software.software_version,
    ),
    GoogleWifiSensorEntityDescription(
        key=ATTR_NEW_VERSION,
        translation_key=ATTR_NEW_VERSION,
        icon="mdi:update",
        value_fn=lambda status: (
            "Latest"
            if status.software.update_new_version == "0.0.0.0"
            else status.software.update_new_version
        ),
    ),
    # deprecated: The uptime sensor is deprecated and will be removed in 2027.4.0. Use last_restart instead.
    GoogleWifiSensorEntityDescription(
        key=ATTR_UPTIME,
        translation_key=ATTR_UPTIME,
        native_unit_of_measurement=UnitOfTime.DAYS,
        icon="mdi:timelapse",
        value_fn=lambda status: round(status.system.uptime / (3600 * 24), 2),
    ),
    GoogleWifiSensorEntityDescription(
        key=ATTR_LAST_RESTART,
        translation_key=ATTR_LAST_RESTART,
        icon="mdi:restart",
        value_fn=lambda status: status.system.last_restart,
    ),
    GoogleWifiSensorEntityDescription(
        key=ATTR_LOCAL_IP,
        translation_key=ATTR_LOCAL_IP,
        icon="mdi:access-point-network",
        value_fn=lambda status: (
            str(status.wan.local_ip_address) if status.wan.online else None
        ),
    ),
    GoogleWifiSensorEntityDescription(
        key=ATTR_STATUS,
        translation_key=ATTR_STATUS,
        icon="mdi:google",
        value_fn=lambda status: "Online" if status.wan.online else "Offline",
    ),
)

SENSOR_KEYS: list[str] = [desc.key for desc in SENSOR_TYPES]

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        probatio.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
        probatio.Optional(CONF_MONITORED_CONDITIONS, default=SENSOR_KEYS): probatio.All(
            probatio.EnsureList(), [probatio.In(SENSOR_KEYS)]
        ),
        probatio.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def _async_create_import_issue(
    hass: HomeAssistant,
    *,
    success: bool,
    reason: str | None = None,
) -> None:
    """Create the repair issue for a YAML import attempt."""
    if success:
        ir.async_create_issue(
            hass,
            HOMEASSISTANT_DOMAIN,
            f"deprecated_yaml_{DOMAIN}",
            breaks_in_ha_version="2027.6.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=ir.IssueSeverity.WARNING,
            translation_key="deprecated_yaml",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": INTEGRATION_TITLE,
            },
        )
        return

    issue_reason = reason if reason in _IMPORT_FAILURE_REASONS else "unknown"
    ir.async_create_issue(
        hass,
        DOMAIN,
        f"deprecated_yaml_import_issue_{issue_reason}",
        breaks_in_ha_version="2027.6.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key=f"deprecated_yaml_import_issue_{issue_reason}",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": INTEGRATION_TITLE,
        },
    )


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Import a YAML Google Wifi sensor into a config entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_HOST: config[CONF_HOST], CONF_NAME: config[CONF_NAME]},
    )
    imported = result["type"] is FlowResultType.CREATE_ENTRY or (
        result["type"] is FlowResultType.ABORT
        and result["reason"] == "already_configured"
    )
    reason = result["reason"] if result["type"] is FlowResultType.ABORT else None
    _async_create_import_issue(hass, success=imported, reason=reason)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GoogleWifiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Google Wifi sensors from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        GoogleWifiSensor(coordinator, description) for description in SENSOR_TYPES
    )


class GoogleWifiSensor(CoordinatorEntity[GoogleWifiCoordinator], SensorEntity):
    """Representation of a Google Wifi sensor."""

    _attr_has_entity_name = True
    entity_description: GoogleWifiSensorEntityDescription

    def __init__(
        self,
        coordinator: GoogleWifiCoordinator,
        description: GoogleWifiSensorEntityDescription,
    ) -> None:
        """Initialize a Google Wifi sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        entry = coordinator.config_entry
        self._attr_unique_id = f"{coordinator.hardware_id}_{description.key}"
        status = coordinator.data
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.hardware_id)},
            name=entry.title,
            manufacturer="Google",
            configuration_url=f"http://{entry.data[CONF_HOST]}",
            model=None if status is None else status.system.model_id,
            sw_version=None if status is None else status.software.software_version,
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
