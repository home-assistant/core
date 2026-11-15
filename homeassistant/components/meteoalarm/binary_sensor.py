"""Binary sensor for MeteoAlarm.eu."""

from datetime import datetime
from typing import Any, override

import probatio

from homeassistant.components.binary_sensor import (
    PLATFORM_SCHEMA as BINARY_SENSOR_PLATFORM_SCHEMA,
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_COUNTRY, CONF_LANGUAGE, CONF_NAME
from homeassistant.core import (
    CALLBACK_TYPE,
    DOMAIN as HOMEASSISTANT_DOMAIN,
    HomeAssistant,
    callback,
)
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.event import async_track_point_in_utc_time
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

    _unsub_expiry: CALLBACK_TYPE | None = None

    @override
    async def async_added_to_hass(self) -> None:
        """Update the state when the current alert expires."""
        await super().async_added_to_hass()
        self.async_on_remove(self._cancel_expiry)
        self._schedule_expiry()

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Follow the expiry time of the newly fetched alert."""
        self._schedule_expiry()
        super()._handle_coordinator_update()

    @callback
    def _schedule_expiry(self) -> None:
        """Write the state again when the current alert expires."""
        self._cancel_expiry()
        if (expires := self._expires(self._current_alert())) is not None:
            self._unsub_expiry = async_track_point_in_utc_time(
                self.hass, self._async_alert_expired, expires
            )

    @callback
    def _cancel_expiry(self) -> None:
        """Cancel the expiry timer."""
        if self._unsub_expiry is not None:
            self._unsub_expiry()
            self._unsub_expiry = None

    @callback
    def _async_alert_expired(self, _now: datetime) -> None:
        """Turn off, or become unavailable while MeteoAlarm can't be reached."""
        self._unsub_expiry = None
        self.async_write_ha_state()

    @property
    @override
    def available(self) -> bool:
        """Stay available with a current alert when MeteoAlarm can't be reached.

        The issuer says how long a warning is valid, so a failed fetch doesn't
        make it stale until it expires. Without a current alert, a failed fetch
        can't confirm there is no new one.
        """
        return super().available or self._current_alert() is not None

    @staticmethod
    def _expires(alert: dict[str, Any] | None) -> datetime | None:
        """Return when the alert expires, if it has a valid expiration time."""
        if alert is None or (raw_expires := alert.get("expires")) is None:
            return None
        return dt_util.parse_datetime(raw_expires)

    def _current_alert(self) -> dict[str, Any] | None:
        """Return the alert if it hasn't expired yet.

        CAP makes expires optional: an alert without one has no known end, so
        it stays current.
        """
        if not (alert := self.coordinator.data):
            return None
        if alert.get("expires") is None:
            return alert
        if (expires := self._expires(alert)) is None or expires <= dt_util.utcnow():
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
