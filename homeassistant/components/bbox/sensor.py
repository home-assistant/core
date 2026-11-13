"""Support for Bbox Bouygues Modem Router sensors."""

from datetime import datetime, timedelta
from typing import override

import probatio

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    CONF_HOST,
    CONF_MONITORED_VARIABLES,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_VERIFY_SSL,
    UnitOfDataRate,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.dt import utcnow

from .const import DEFAULT_HOST, DEFAULT_NAME, DOMAIN, INTEGRATION_TITLE
from .coordinator import BboxConfigEntry, BboxCoordinator

ATTRIBUTION = "Powered by Bouygues Telecom"

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="down_max_bandwidth",
        translation_key="down_max_bandwidth",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        icon="mdi:download",
    ),
    SensorEntityDescription(
        key="up_max_bandwidth",
        translation_key="up_max_bandwidth",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        icon="mdi:upload",
    ),
    SensorEntityDescription(
        key="current_down_bandwidth",
        translation_key="current_down_bandwidth",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:download",
    ),
    SensorEntityDescription(
        key="current_up_bandwidth",
        translation_key="current_up_bandwidth",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:upload",
    ),
    SensorEntityDescription(
        key="number_of_reboots",
        translation_key="number_of_reboots",
        icon="mdi:restart",
    ),
)

SENSOR_TYPES_UPTIME: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="uptime",
        translation_key="uptime",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:clock",
    ),
)

SENSOR_KEYS: list[str] = [desc.key for desc in (*SENSOR_TYPES, *SENSOR_TYPES_UPTIME)]

# The legacy YAML structure is kept as-is: it is imported into a config
# entry by async_setup_platform below, new options live in the config flow.
# host/password/verify_ssl stay accepted so a YAML written for them still
# imports into the entry instead of failing schema validation.
PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        probatio.Required(CONF_MONITORED_VARIABLES): probatio.All(
            probatio.EnsureList(), [probatio.In(SENSOR_KEYS)]
        ),
        probatio.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        probatio.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
        probatio.Optional(CONF_PASSWORD, default=""): cv.string,
        probatio.Optional(CONF_VERIFY_SSL, default=True): cv.boolean,
    }
)

# All entities consume coordinator data, so they never poll independently.
PARALLEL_UPDATES = 0


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Import the legacy YAML sensor platform configuration."""
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config
        )
    )
    ir.async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version="2027.2.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": INTEGRATION_TITLE,
        },
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BboxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Bbox sensors from a config entry."""
    coordinator = entry.runtime_data
    name = entry.data.get(CONF_NAME, DEFAULT_NAME)
    monitored_variables = entry.data.get(CONF_MONITORED_VARIABLES, SENSOR_KEYS)
    async_add_entities(
        BboxSensor(coordinator, name, description)
        for description in (*SENSOR_TYPES, *SENSOR_TYPES_UPTIME)
        if description.key in monitored_variables
    )


class BboxSensor(CoordinatorEntity[BboxCoordinator], SensorEntity):
    """Implementation of a Bbox sensor."""

    _attr_attribution = ATTRIBUTION
    # The entity name comes from the translations and is prefixed with the
    # device name (the configured name, "Bbox" by default), which keeps the
    # legacy entity ids (sensor.bbox_...).
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BboxCoordinator,
        name: str,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}-{description.key}"
        device = coordinator.data.device
        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, device.serialnumber or coordinator.config_entry.entry_id)
            },
            name=name,
            manufacturer="Bouygues Telecom",
            model=device.modelname,
            sw_version=device.firmware_version,
        )

    @property
    @override
    def native_value(self) -> float | int | datetime | None:
        """Return the value of the sensor from the coordinator data."""
        data = self.coordinator.data
        sensor_type = self.entity_description.key
        if sensor_type == "down_max_bandwidth":
            return round(data.stats.rx.max_bandwidth_mbps, 2)
        if sensor_type == "up_max_bandwidth":
            return round(data.stats.tx.max_bandwidth_mbps, 2)
        if sensor_type == "current_down_bandwidth":
            return round(data.stats.rx.bandwidth_mbps, 2)
        if sensor_type == "current_up_bandwidth":
            return round(data.stats.tx.bandwidth_mbps, 2)
        if sensor_type == "number_of_reboots":
            return data.device.numberofboots
        if sensor_type == "uptime":
            return utcnow() - timedelta(seconds=data.device.uptime)
        return None
