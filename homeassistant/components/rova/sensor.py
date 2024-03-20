"""Support for Rova garbage calendar."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from requests.exceptions import ConnectTimeout, HTTPError
from rova.rova import Rova
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_MONITORED_CONDITIONS, CONF_NAME
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import Throttle
from homeassistant.util.dt import get_time_zone

from .const import (
    CONF_HOUSE_NUMBER,
    CONF_HOUSE_NUMBER_SUFFIX,
    CONF_ZIP_CODE,
    DOMAIN,
    LOGGER,
)

ISSUE_PLACEHOLDER = {"url": "/config/integrations/dashboard/add?domain=rova"}

UPDATE_DELAY = timedelta(hours=12)
SCAN_INTERVAL = timedelta(hours=12)

SENSOR_TYPES = {
    "bio": SensorEntityDescription(
        key="gft",
        name="bio",
        icon="mdi:recycle",
    ),
    "paper": SensorEntityDescription(
        key="papier",
        name="paper",
        icon="mdi:recycle",
    ),
    "plastic": SensorEntityDescription(
        key="pmd",
        name="plastic",
        icon="mdi:recycle",
    ),
    "residual": SensorEntityDescription(
        key="restafval",
        name="residual",
        icon="mdi:recycle",
    ),
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ZIP_CODE): cv.string,
        vol.Required(CONF_HOUSE_NUMBER): cv.string,
        vol.Optional(CONF_HOUSE_NUMBER_SUFFIX, default=""): cv.string,
        vol.Optional(CONF_NAME, default="Rova"): cv.string,
        vol.Optional(CONF_MONITORED_CONDITIONS, default=["bio"]): vol.All(
            cv.ensure_list, [vol.In(SENSOR_TYPES)]
        ),
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the rova sensor platform through yaml configuration."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=config,
    )
    if (
        result["type"] == FlowResultType.CREATE_ENTRY
        or result["reason"] == "already_configured"
    ):
        async_create_issue(
            hass,
            HOMEASSISTANT_DOMAIN,
            f"deprecated_yaml_{DOMAIN}",
            breaks_in_ha_version="2024.10.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_yaml",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "Rova",
            },
        )
    else:
        async_create_issue(
            hass,
            DOMAIN,
            f"deprecated_yaml_import_issue_${result['reason']}",
            breaks_in_ha_version="2024.10.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=IssueSeverity.WARNING,
            translation_key=f"deprecated_yaml_import_issue_${result['reason']}",
            translation_placeholders=ISSUE_PLACEHOLDER,
        )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add Rova entry."""
    # get api from hass
    api: Rova = hass.data[DOMAIN][entry.entry_id]

    # Create rova data service which will retrieve and update the data.
    data_service = RovaData(api)

    # generate unique name for rova integration
    name = f"{entry.data[CONF_ZIP_CODE]}{entry.data[CONF_HOUSE_NUMBER]}{entry.data[CONF_HOUSE_NUMBER_SUFFIX]}"

    # Create a new sensor for each garbage type.
    entities = [
        RovaSensor(name, description, data_service)
        for key, description in SENSOR_TYPES.items()
    ]
    async_add_entities(entities, True)


class RovaSensor(SensorEntity):
    """Representation of a Rova sensor."""

    def __init__(
        self, platform_name, description: SensorEntityDescription, data_service
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = description
        self.data_service = data_service

        self._attr_name = f"{platform_name}_{description.key}"
        self._attr_unique_id = f"{platform_name}_{description.key}"
        self._attr_device_class = SensorDeviceClass.TIMESTAMP

    def update(self) -> None:
        """Get the latest data from the sensor and update the state."""
        self.data_service.update()
        pickup_date = self.data_service.data.get(self.entity_description.key)
        if pickup_date is not None:
            self._attr_native_value = pickup_date


class RovaData:
    """Get and update the latest data from the Rova API."""

    def __init__(self, api) -> None:
        """Initialize the data object."""
        self.api = api
        self.data: dict[str, Any] = {}

    @Throttle(UPDATE_DELAY)
    def update(self):
        """Update the data from the Rova API."""

        try:
            items = self.api.get_calendar_items()
        except (ConnectTimeout, HTTPError):
            LOGGER.error("Could not retrieve data, retry again later")
            return

        self.data = {}

        for item in items:
            date = datetime.strptime(item["Date"], "%Y-%m-%dT%H:%M:%S").replace(
                tzinfo=get_time_zone("Europe/Amsterdam")
            )
            code = item["GarbageTypeCode"].lower()
            if code not in self.data:
                self.data[code] = date

        LOGGER.debug("Updated Rova calendar: %s", self.data)
