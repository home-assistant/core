"""Binary sensor for MeteoAlarm.eu."""

from datetime import timedelta
from typing import Any

import probatio

from homeassistant.components.binary_sensor import (
    PLATFORM_SCHEMA as BINARY_SENSOR_PLATFORM_SCHEMA,
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_COUNTRY, CONF_LANGUAGE, CONF_NAME
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import dt as dt_util, slugify

from . import MeteoAlarmConfigEntry
from .const import ATTRIBUTION, CONF_PROVINCE, DEFAULT_LANGUAGE, DEFAULT_NAME, DOMAIN

SCAN_INTERVAL = timedelta(minutes=5)

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
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_COUNTRY: config[CONF_COUNTRY],
            CONF_PROVINCE: config[CONF_PROVINCE],
            CONF_LANGUAGE: config[CONF_LANGUAGE],
            CONF_NAME: config[CONF_NAME],
        },
    )

    if (
        result["type"] is FlowResultType.ABORT
        and (reason := result["reason"]) != "already_configured"
    ):
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
    # The sensor starts from the alert fetched during setup.
    async_add_entities([MeteoAlertBinarySensor(entry)])


class MeteoAlertBinarySensor(BinarySensorEntity):
    """On while the region has a current alert, with its details as attributes."""

    _attr_attribution = ATTRIBUTION
    _attr_device_class = BinarySensorDeviceClass.SAFETY
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, entry: MeteoAlarmConfigEntry) -> None:
        """Initialize the MeteoAlarm binary sensor."""
        self._api = entry.runtime_data.api
        self._attr_unique_id = entry.entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="MeteoAlarm",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://meteoalarm.org",
        )
        self._set_alert(entry.runtime_data.alert)

    def update(self) -> None:
        """Fetch the region's most severe alert."""
        self._set_alert(self._api.get_alert())

    def _set_alert(self, alert: dict[str, Any]) -> None:
        """Show the alert while it hasn't expired."""
        self._attr_extra_state_attributes = {}
        self._attr_is_on = False

        if alert:
            # An alert without an expiration time stays active until the feed
            # stops returning it.
            if (expires := alert.get("expires")) is None or (
                (expiration_date := dt_util.parse_datetime(expires)) is not None
                and expiration_date > dt_util.utcnow()
            ):
                self._attr_extra_state_attributes = {
                    key: (
                        value.encode("utf-8", errors="replace").decode("utf-8")
                        if isinstance(value, str)
                        else value
                    )
                    for key, value in alert.items()
                }
                self._attr_is_on = True
