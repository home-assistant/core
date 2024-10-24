"""Binary Sensor for MeteoAlarm.eu."""

from __future__ import annotations

from datetime import timedelta

from meteoalertapi import Meteoalert
import voluptuous as vol

from homeassistant.components.binary_sensor import (
    PLATFORM_SCHEMA as BINARY_SENSOR_PLATFORM_SCHEMA,
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
import homeassistant.util.dt as dt_util

from .const import (
    ATTRIBUTION,
    CONF_COUNTRY,
    CONF_LANGUAGE,
    CONF_PROVINCE,
    DOMAIN,
    LOGGER,
)

SCAN_INTERVAL = timedelta(minutes=5)

PLATFORM_SCHEMA = BINARY_SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_COUNTRY): cv.string,
        vol.Required(CONF_PROVINCE): cv.string,
        vol.Optional(CONF_LANGUAGE, default="en"): cv.string,
        vol.Optional(CONF_NAME, default=DOMAIN): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the MeteoAlarm binary sensor platform."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=config,
    )
    if (
        result["type"] is FlowResultType.CREATE_ENTRY
        or result["reason"] == "single_instance_allowed"
    ):
        async_create_issue(
            hass,
            HOMEASSISTANT_DOMAIN,
            f"deprecated_yaml_{DOMAIN}",
            breaks_in_ha_version="2025.3.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_yaml",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "MeteoAlarm",
            },
        )
        return
    async_create_issue(
        hass,
        DOMAIN,
        f"deprecated_yaml_import_issue_{result['reason']}",
        breaks_in_ha_version="2025.3.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=IssueSeverity.WARNING,
        translation_key=f"deprecated_yaml_import_issue_{result['reason']}",
        translation_placeholders={"domain": DOMAIN, "integration_title": "MeteoAlarm"},
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up MeteoAlarm from config_entry."""

    try:
        Meteoalert(
            entry.data[CONF_COUNTRY],
            entry.data[CONF_PROVINCE],
            entry.data[CONF_LANGUAGE],
        )
    except KeyError:
        LOGGER.error("Wrong country digits or province name")
        return

    async_add_entities([MeteoAlertBinarySensor(entry)], True)


class MeteoAlertBinarySensor(BinarySensorEntity):
    """Representation of a MeteoAlert binary sensor."""

    _attr_attribution = ATTRIBUTION
    _attr_device_class = BinarySensorDeviceClass.SAFETY

    def __init__(self, config: ConfigEntry, entry_id: str | None = None) -> None:
        """Initialize the MeteoAlert binary sensor."""
        self._api = Meteoalert(
            country=config.data.get(CONF_COUNTRY),
            province=config.data.get(CONF_PROVINCE),
            language=config.data.get(CONF_LANGUAGE),
        )
        self._attr_unique_id = (
            f"{self._api.country}_{self._api.province}_{self._api.language}"
        )

    def update(self) -> None:
        """Update device state."""
        self._attr_extra_state_attributes = {}
        self._attr_is_on = False

        if alert := self._api.get_alert():
            expiration_date = dt_util.parse_datetime(alert["expires"])

            if expiration_date is not None and expiration_date > dt_util.utcnow():
                self._attr_extra_state_attributes = alert
                self._attr_is_on = True
