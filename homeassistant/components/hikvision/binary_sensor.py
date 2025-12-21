"""Support for Hikvision event stream events represented as binary sensors."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    PLATFORM_SCHEMA as BINARY_SENSOR_PLATFORM_SCHEMA,
    BinarySensorDeviceClass,
    BinarySensorEntity,
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
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import HikvisionConfigEntry
from .const import DEFAULT_PORT, DOMAIN

CONF_IGNORED = "ignored"

DEFAULT_DELAY = 0
DEFAULT_IGNORED = False

# Device class mapping for Hikvision event types
DEVICE_CLASS_MAP: dict[str, BinarySensorDeviceClass | None] = {
    "Motion": BinarySensorDeviceClass.MOTION,
    "Line Crossing": BinarySensorDeviceClass.MOTION,
    "Field Detection": BinarySensorDeviceClass.MOTION,
    "Tamper Detection": BinarySensorDeviceClass.MOTION,
    "Shelter Alarm": None,
    "Disk Full": None,
    "Disk Error": None,
    "Net Interface Broken": BinarySensorDeviceClass.CONNECTIVITY,
    "IP Conflict": BinarySensorDeviceClass.CONNECTIVITY,
    "Illegal Access": None,
    "Video Mismatch": None,
    "Bad Video": None,
    "PIR Alarm": BinarySensorDeviceClass.MOTION,
    "Face Detection": BinarySensorDeviceClass.MOTION,
    "Scene Change Detection": BinarySensorDeviceClass.MOTION,
    "I/O": None,
    "Unattended Baggage": BinarySensorDeviceClass.MOTION,
    "Attended Baggage": BinarySensorDeviceClass.MOTION,
    "Recording Failure": None,
    "Exiting Region": BinarySensorDeviceClass.MOTION,
    "Entering Region": BinarySensorDeviceClass.MOTION,
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
        _LOGGER.warning("Hikvision device has no sensors available")
        return

    async_add_entities(
        HikvisionBinarySensor(
            entry=entry,
            sensor_type=sensor_type,
            channel=channel_info[1],
        )
        for sensor_type, channel_list in sensors.items()
        for channel_info in channel_list
    )


class HikvisionBinarySensor(BinarySensorEntity):
    """Representation of a Hikvision binary sensor."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        entry: HikvisionConfigEntry,
        sensor_type: str,
        channel: int,
    ) -> None:
        """Initialize the binary sensor."""
        self._data = entry.runtime_data
        self._camera = self._data.camera
        self._sensor_type = sensor_type
        self._channel = channel

        # Build unique ID
        self._attr_unique_id = f"{self._data.device_id}_{sensor_type}_{channel}"

        # Build entity name based on device type
        if self._data.device_type == "NVR":
            self._attr_name = f"{sensor_type} {channel}"
        else:
            self._attr_name = sensor_type

        # Device info for device registry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._data.device_id)},
            name=self._data.device_name,
            manufacturer="Hikvision",
            model=self._data.device_type,
        )

        # Set device class
        self._attr_device_class = DEVICE_CLASS_MAP.get(sensor_type)

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

    @callback
    def _update_callback(self, msg: str) -> None:
        """Update the sensor's state when callback is triggered."""
        self.async_write_ha_state()
