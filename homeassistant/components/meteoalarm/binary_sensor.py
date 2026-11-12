"""Binary sensor for MeteoAlarm.eu."""

from typing import Any, override

import probatio

from homeassistant.components.binary_sensor import (
    PLATFORM_SCHEMA as BINARY_SENSOR_PLATFORM_SCHEMA,
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    CONF_COUNTRY,
    CONF_ENTITY_NAMESPACE,
    CONF_LANGUAGE,
    CONF_NAME,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util, slugify

from .const import ATTRIBUTION, CONF_PROVINCE, DEFAULT_LANGUAGE, DEFAULT_NAME, DOMAIN
from .coordinator import MeteoAlarmConfigEntry, MeteoAlarmCoordinator

PARALLEL_UPDATES = 0

BREAKS_IN_HA_VERSION = "2027.6.0"

PLATFORM_SCHEMA = BINARY_SENSOR_PLATFORM_SCHEMA.extend(
    {
        probatio.Required(CONF_COUNTRY): cv.string,
        probatio.Required(CONF_PROVINCE): cv.string,
        probatio.Optional(CONF_LANGUAGE, default=DEFAULT_LANGUAGE): cv.string,
        probatio.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Import the legacy YAML configuration into a config entry."""
    name = config[CONF_NAME]
    # The entity ID comes from the entry title, so keep the namespace that the
    # YAML platform put in front of it.
    if namespace := config.get(CONF_ENTITY_NAMESPACE):
        name = f"{namespace} {name}"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_COUNTRY: config[CONF_COUNTRY],
            CONF_PROVINCE: config[CONF_PROVINCE],
            CONF_LANGUAGE: config[CONF_LANGUAGE],
            CONF_NAME: name,
        },
    )

    if result["type"] is FlowResultType.ABORT:
        reason = result["reason"]
        if reason == "already_in_progress":
            # The same region is configured twice; the first import reports.
            return
        if reason != "already_configured":
            region = slugify(
                f"{config[CONF_COUNTRY]}_{config[CONF_PROVINCE]}_{config[CONF_LANGUAGE]}"
            )
            ir.async_create_issue(
                hass,
                DOMAIN,
                f"deprecated_yaml_import_issue_{reason}_{region}",
                breaks_in_ha_version=BREAKS_IN_HA_VERSION,
                is_fixable=False,
                issue_domain=DOMAIN,
                severity=ir.IssueSeverity.WARNING,
                translation_key=f"deprecated_yaml_import_issue_{reason}",
                translation_placeholders={
                    "country": config[CONF_COUNTRY],
                    "province": config[CONF_PROVINCE],
                },
            )
            return

    ir.async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version=BREAKS_IN_HA_VERSION,
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": "MeteoAlarm",
        },
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MeteoAlarmConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the MeteoAlarm binary sensor from a config entry."""
    async_add_entities([MeteoAlertBinarySensor(entry.runtime_data)])


class MeteoAlertBinarySensor(
    CoordinatorEntity[MeteoAlarmCoordinator], BinarySensorEntity
):
    """On while the region has a current alert, with its details as attributes."""

    _attr_attribution = ATTRIBUTION
    _attr_device_class = BinarySensorDeviceClass.SAFETY
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, coordinator: MeteoAlarmCoordinator) -> None:
        """Initialize the MeteoAlarm binary sensor."""
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_unique_id = entry.entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="MeteoAlarm",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://meteoalarm.org",
        )

    def _current_alert(self) -> dict[str, Any] | None:
        """Return the alert if it hasn't expired yet.

        CAP makes expires optional: an alert without one has no known end, so
        it stays current.
        """
        if not (alert := self.coordinator.data):
            return None
        if (raw_expires := alert.get("expires")) is None:
            return alert
        expires = dt_util.parse_datetime(raw_expires)
        if expires is None or expires <= dt_util.utcnow():
            return None
        return alert

    @property
    @override
    def is_on(self) -> bool:
        """Return true while there is a current alert."""
        return self._current_alert() is not None

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the current alert's details."""
        if (alert := self._current_alert()) is None:
            return {}
        return {
            key: (
                value.encode("utf-8", errors="replace").decode("utf-8")
                if isinstance(value, str)
                else value
            )
            for key, value in alert.items()
        }
