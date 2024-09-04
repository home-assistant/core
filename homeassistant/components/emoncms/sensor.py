"""Support for monitoring emoncms feeds."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_ID,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_URL,
    CONF_VALUE_TEMPLATE,
    UnitOfPower,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import template
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .config_flow import sensor_name
from .const import (
    CONF_EXCLUDE_FEEDID,
    CONF_ONLY_INCLUDE_FEEDID,
    DOMAIN,
    FEED_ID,
    FEED_NAME,
    FEED_TAG,
)
from .coordinator import EmoncmsCoordinator

ATTR_FEEDID = "FeedId"
ATTR_FEEDNAME = "FeedName"
ATTR_LASTUPDATETIME = "LastUpdated"
ATTR_LASTUPDATETIMESTR = "LastUpdatedStr"
ATTR_SIZE = "Size"
ATTR_TAG = "Tag"
ATTR_USERID = "UserId"
CONF_SENSOR_NAMES = "sensor_names"
DECIMALS = 2
DEFAULT_UNIT = UnitOfPower.WATT

ONLY_INCL_EXCL_NONE = "only_include_exclude_or_none"

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_URL): cv.string,
        vol.Required(CONF_ID): cv.positive_int,
        vol.Exclusive(CONF_ONLY_INCLUDE_FEEDID, ONLY_INCL_EXCL_NONE): vol.All(
            cv.ensure_list, [cv.positive_int]
        ),
        vol.Exclusive(CONF_EXCLUDE_FEEDID, ONLY_INCL_EXCL_NONE): vol.All(
            cv.ensure_list, [cv.positive_int]
        ),
        vol.Optional(CONF_SENSOR_NAMES): vol.All(
            {cv.positive_int: vol.All(cv.string, vol.Length(min=1))}
        ),
        vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
        vol.Optional(CONF_UNIT_OF_MEASUREMENT, default=DEFAULT_UNIT): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Import config from yaml."""
    if CONF_VALUE_TEMPLATE in config:
        async_create_issue(
            hass,
            DOMAIN,
            f"remove_{CONF_VALUE_TEMPLATE}_{DOMAIN}",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=IssueSeverity.ERROR,
            translation_key=f"remove_{CONF_VALUE_TEMPLATE}",
            translation_placeholders={
                "domain": DOMAIN,
                "parameter": CONF_VALUE_TEMPLATE,
            },
        )
        return
    if CONF_ONLY_INCLUDE_FEEDID not in config:
        async_create_issue(
            hass,
            DOMAIN,
            f"missing_{CONF_ONLY_INCLUDE_FEEDID}_{DOMAIN}",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=IssueSeverity.WARNING,
            translation_key=f"missing_{CONF_ONLY_INCLUDE_FEEDID}",
            translation_placeholders={
                "domain": DOMAIN,
            },
        )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=config
    )
    if (
        result.get("type") == FlowResultType.CREATE_ENTRY
        or result.get("reason") == "already_configured"
    ):
        async_create_issue(
            hass,
            HOMEASSISTANT_DOMAIN,
            f"deprecated_yaml_{DOMAIN}",
            is_fixable=False,
            issue_domain=DOMAIN,
            breaks_in_ha_version="2025.3.0",
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_yaml",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "emoncms",
            },
        )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the emoncms sensors."""
    config = entry.options if entry.options else entry.data
    name = sensor_name(config[CONF_URL])
    exclude_feeds = config.get(CONF_EXCLUDE_FEEDID)
    include_only_feeds = config.get(CONF_ONLY_INCLUDE_FEEDID)

    if exclude_feeds is None and include_only_feeds is None:
        return

    coordinator = entry.runtime_data
    elems = coordinator.data
    if not elems:
        return

    sensors: list[EmonCmsSensor] = []

    for idx, elem in enumerate(elems):
        if include_only_feeds is not None and elem[FEED_ID] not in include_only_feeds:
            continue

        sensors.append(
            EmonCmsSensor(
                coordinator,
                entry.entry_id,
                elem["unit"],
                name,
                idx,
            )
        )
    async_add_entities(sensors)


class EmonCmsSensor(CoordinatorEntity[EmoncmsCoordinator], SensorEntity):
    """Implementation of an Emoncms sensor."""

    def __init__(
        self,
        coordinator: EmoncmsCoordinator,
        entry_id: str,
        unit_of_measurement: str | None,
        name: str,
        idx: int,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.idx = idx
        elem = {}
        if self.coordinator.data:
            elem = self.coordinator.data[self.idx]
        self._attr_name = f"{name} {elem[FEED_NAME]}"
        self._attr_native_unit_of_measurement = unit_of_measurement
        self._attr_unique_id = f"{entry_id}-{elem[FEED_ID]}"
        if unit_of_measurement in ("kWh", "Wh"):
            self._attr_device_class = SensorDeviceClass.ENERGY
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        elif unit_of_measurement == "W":
            self._attr_device_class = SensorDeviceClass.POWER
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif unit_of_measurement == "V":
            self._attr_device_class = SensorDeviceClass.VOLTAGE
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif unit_of_measurement == "A":
            self._attr_device_class = SensorDeviceClass.CURRENT
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif unit_of_measurement == "VA":
            self._attr_device_class = SensorDeviceClass.APPARENT_POWER
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif unit_of_measurement in ("°C", "°F", "K"):
            self._attr_device_class = SensorDeviceClass.TEMPERATURE
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif unit_of_measurement == "Hz":
            self._attr_device_class = SensorDeviceClass.FREQUENCY
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif unit_of_measurement == "hPa":
            self._attr_device_class = SensorDeviceClass.PRESSURE
            self._attr_state_class = SensorStateClass.MEASUREMENT
        self._update_attributes(elem)

    def _update_attributes(self, elem: dict[str, Any]) -> None:
        """Update entity attributes."""
        self._attr_extra_state_attributes = {
            ATTR_FEEDID: elem[FEED_ID],
            ATTR_TAG: elem[FEED_TAG],
            ATTR_FEEDNAME: elem[FEED_NAME],
        }
        if elem["value"] is not None:
            self._attr_extra_state_attributes[ATTR_SIZE] = elem["size"]
            self._attr_extra_state_attributes[ATTR_USERID] = elem["userid"]
            self._attr_extra_state_attributes[ATTR_LASTUPDATETIME] = elem["time"]
            self._attr_extra_state_attributes[ATTR_LASTUPDATETIMESTR] = (
                template.timestamp_local(float(elem["time"]))
            )

        self._attr_native_value = None
        if elem["value"] is not None:
            self._attr_native_value = round(float(elem["value"]), DECIMALS)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        data = self.coordinator.data
        if data:
            self._update_attributes(data[self.idx])
        super()._handle_coordinator_update()
