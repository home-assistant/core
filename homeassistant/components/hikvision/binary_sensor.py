"""Support for Hikvision event stream events represented as binary sensors."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    PLATFORM_SCHEMA as BINARY_SENSOR_PLATFORM_SCHEMA,
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    ATTR_LAST_TRIP_TIME,
    CONF_CUSTOMIZE,
    CONF_DELAY,
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    EntityCategory,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import HikvisionConfigEntry
from .const import DEFAULT_PORT, DOMAIN
from .entity import HikvisionEntity

CONF_IGNORED = "ignored"

DEFAULT_DELAY = 0
DEFAULT_IGNORED = False


# Entity descriptions for known Hikvision event types
# The key matches the sensor_type from pyhik (the friendly name from SENSOR_MAP)
BINARY_SENSOR_DESCRIPTIONS: dict[str, BinarySensorEntityDescription] = {
    "Motion": BinarySensorEntityDescription(
        key="motion",
        device_class=BinarySensorDeviceClass.MOTION,
    ),
    "Line Crossing": BinarySensorEntityDescription(
        key="line_crossing",
        translation_key="line_crossing",
        device_class=BinarySensorDeviceClass.MOTION,
    ),
    "Field Detection": BinarySensorEntityDescription(
        key="field_detection",
        translation_key="field_detection",
        device_class=BinarySensorDeviceClass.MOTION,
    ),
    "Tamper Detection": BinarySensorEntityDescription(
        key="tamper_detection",
        device_class=BinarySensorDeviceClass.TAMPER,
    ),
    "Shelter Alarm": BinarySensorEntityDescription(
        key="shelter_alarm",
        translation_key="shelter_alarm",
    ),
    "Disk Full": BinarySensorEntityDescription(
        key="disk_full",
        translation_key="disk_full",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "Disk Error": BinarySensorEntityDescription(
        key="disk_error",
        translation_key="disk_error",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "Net Interface Broken": BinarySensorEntityDescription(
        key="net_interface_broken",
        translation_key="net_interface_broken",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "IP Conflict": BinarySensorEntityDescription(
        key="ip_conflict",
        translation_key="ip_conflict",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "Illegal Access": BinarySensorEntityDescription(
        key="illegal_access",
        translation_key="illegal_access",
        device_class=BinarySensorDeviceClass.SAFETY,
    ),
    "Video Mismatch": BinarySensorEntityDescription(
        key="video_mismatch",
        translation_key="video_mismatch",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "Bad Video": BinarySensorEntityDescription(
        key="bad_video",
        translation_key="bad_video",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "PIR Alarm": BinarySensorEntityDescription(
        key="pir_alarm",
        translation_key="pir_alarm",
        device_class=BinarySensorDeviceClass.MOTION,
    ),
    "Face Detection": BinarySensorEntityDescription(
        key="face_detection",
        translation_key="face_detection",
        device_class=BinarySensorDeviceClass.MOTION,
    ),
    "Scene Change Detection": BinarySensorEntityDescription(
        key="scene_change_detection",
        translation_key="scene_change_detection",
        device_class=BinarySensorDeviceClass.MOTION,
    ),
    "I/O": BinarySensorEntityDescription(
        key="io",
        translation_key="io",
    ),
    "Unattended Baggage": BinarySensorEntityDescription(
        key="unattended_baggage",
        translation_key="unattended_baggage",
        device_class=BinarySensorDeviceClass.MOTION,
    ),
    "Attended Baggage": BinarySensorEntityDescription(
        key="attended_baggage",
        translation_key="attended_baggage",
        device_class=BinarySensorDeviceClass.MOTION,
    ),
    "Recording Failure": BinarySensorEntityDescription(
        key="recording_failure",
        translation_key="recording_failure",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "Exiting Region": BinarySensorEntityDescription(
        key="exiting_region",
        translation_key="exiting_region",
        device_class=BinarySensorDeviceClass.MOTION,
    ),
    "Entering Region": BinarySensorEntityDescription(
        key="entering_region",
        translation_key="entering_region",
        device_class=BinarySensorDeviceClass.MOTION,
    ),
}

_LOGGER = logging.getLogger(__name__)

CUSTOMIZE_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_IGNORED, default=DEFAULT_IGNORED): cv.boolean,
        vol.Optional(CONF_DELAY, default=DEFAULT_DELAY): cv.positive_int,
    }
)

PLATFORM_SCHEMA = BINARY_SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME): cv.string,
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_SSL, default=False): cv.boolean,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_CUSTOMIZE, default={}): vol.Schema(
            {cv.string: CUSTOMIZE_SCHEMA}
        ),
    }
)

PARALLEL_UPDATES = 0


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Hikvision binary sensor platform from YAML."""
    # Trigger the import flow to migrate YAML config to config entry
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=config
    )

    if (
        result.get("type") is FlowResultType.ABORT
        and result.get("reason") != "already_configured"
    ):
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"deprecated_yaml_import_issue_{result.get('reason')}",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=ir.IssueSeverity.WARNING,
            translation_key="deprecated_yaml_import_issue",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "Hikvision",
            },
        )
        return

    ir.async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": "Hikvision",
        },
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HikvisionConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Hikvision binary sensors from a config entry."""
    data = entry.runtime_data
    camera = data.camera

    sensors = camera.current_event_states
    if sensors is None or not sensors:
        _LOGGER.warning(
            "Hikvision %s %s has no sensors available. "
            "Ensure event detection is enabled and configured on the device",
            data.device_type,
            data.device_name,
        )
        return

    # Log warnings for unknown sensor types and skip them
    for sensor_type in sensors:
        if sensor_type not in BINARY_SENSOR_DESCRIPTIONS:
            _LOGGER.warning(
                "Unknown Hikvision sensor type '%s', please report this at "
                "https://github.com/home-assistant/core/issues",
                sensor_type,
            )

    async_add_entities(
        HikvisionBinarySensor(
            entry=entry,
            description=BINARY_SENSOR_DESCRIPTIONS[sensor_type],
            sensor_type=sensor_type,
            channel=channel_info[1],
        )
        for sensor_type, channel_list in sensors.items()
        if sensor_type in BINARY_SENSOR_DESCRIPTIONS
        for channel_info in channel_list
    )


class HikvisionBinarySensor(HikvisionEntity, BinarySensorEntity):
    """Representation of a Hikvision binary sensor."""

    _attr_should_poll = False

    def __init__(
        self,
        entry: HikvisionConfigEntry,
        description: BinarySensorEntityDescription,
        sensor_type: str,
        channel: int,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(entry, channel)
        self.entity_description = description
        self._sensor_type = sensor_type

        # Build unique ID (includes sensor_type for uniqueness per sensor)
        self._attr_unique_id = f"{self._data.device_id}_{sensor_type}_{channel}"

        # Callback ID for pyhik
        self._callback_id = f"{self._data.device_id}.{sensor_type}.{channel}"

    def _get_sensor_attributes(self) -> tuple[bool, Any, Any, Any]:
        """Get sensor attributes from camera."""
        return self._camera.fetch_attributes(self._sensor_type, self._channel)

    @property
    def is_on(self) -> bool:
        """Return true if sensor is on."""
        return self._get_sensor_attributes()[0]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        attrs = self._get_sensor_attributes()
        return {ATTR_LAST_TRIP_TIME: attrs[3]}

    async def async_added_to_hass(self) -> None:
        """Register callback when entity is added."""
        await super().async_added_to_hass()

        # Register callback with pyhik
        self._camera.add_update_callback(self._update_callback, self._callback_id)

    def _update_callback(self, msg: str) -> None:
        """Update the sensor's state when callback is triggered.

        This is called from pyhik's event stream thread, so we use
        schedule_update_ha_state which is thread-safe.
        """
        self.schedule_update_ha_state()
