"""Support for monitoring an SABnzbd NZB client."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    DATA_GIGABYTES,
    DATA_MEGABYTES,
    DATA_RATE_MEGABYTES_PER_SECOND,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN, SIGNAL_SABNZBD_UPDATED
from .const import DEFAULT_NAME, KEY_API_DATA, KEY_NAME


@dataclass
class SabnzbdRequiredKeysMixin:
    """Mixin for required keys."""

    key: str


@dataclass
class SabnzbdSensorEntityDescription(SensorEntityDescription, SabnzbdRequiredKeysMixin):
    """Describes Sabnzbd sensor entity."""


SPEED_KEY = "kbpersec"

SENSOR_TYPES: tuple[SabnzbdSensorEntityDescription, ...] = (
    SabnzbdSensorEntityDescription(
        key="status",
        name="Status",
    ),
    SabnzbdSensorEntityDescription(
        key=SPEED_KEY,
        name="Speed",
        native_unit_of_measurement=DATA_RATE_MEGABYTES_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SabnzbdSensorEntityDescription(
        key="mb",
        name="Queue",
        native_unit_of_measurement=DATA_MEGABYTES,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SabnzbdSensorEntityDescription(
        key="mbleft",
        name="Left",
        native_unit_of_measurement=DATA_MEGABYTES,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SabnzbdSensorEntityDescription(
        key="diskspacetotal1",
        name="Disk",
        native_unit_of_measurement=DATA_GIGABYTES,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SabnzbdSensorEntityDescription(
        key="diskspace1",
        name="Disk Free",
        native_unit_of_measurement=DATA_GIGABYTES,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SabnzbdSensorEntityDescription(
        key="noofslots_total",
        name="Queue Count",
        state_class=SensorStateClass.TOTAL,
    ),
    SabnzbdSensorEntityDescription(
        key="day_size",
        name="Daily Total",
        native_unit_of_measurement=DATA_GIGABYTES,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SabnzbdSensorEntityDescription(
        key="week_size",
        name="Weekly Total",
        native_unit_of_measurement=DATA_GIGABYTES,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SabnzbdSensorEntityDescription(
        key="month_size",
        name="Monthly Total",
        native_unit_of_measurement=DATA_GIGABYTES,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SabnzbdSensorEntityDescription(
        key="total_size",
        name="Total",
        native_unit_of_measurement=DATA_GIGABYTES,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
)

OLD_SENSOR_KEYS = [
    "current_status",
    "speed",
    "queue_size",
    "queue_remaining",
    "disk_size",
    "disk_free",
    "queue_count",
    "day_size",
    "week_size",
    "month_size",
    "total_size",
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a Sabnzbd sensor entry."""

    entry_id = config_entry.entry_id

    sab_api_data = hass.data[DOMAIN][entry_id][KEY_API_DATA]
    client_name = hass.data[DOMAIN][entry_id][KEY_NAME]

    async_add_entities(
        [
            SabnzbdSensor(sab_api_data, client_name, sensor, entry_id)
            for sensor in SENSOR_TYPES
        ]
    )


class SabnzbdSensor(SensorEntity):
    """Representation of an SABnzbd sensor."""

    entity_description: SabnzbdSensorEntityDescription
    _attr_should_poll = False

    def __init__(
        self,
        sabnzbd_api_data,
        client_name,
        description: SabnzbdSensorEntityDescription,
        entry_id,
    ):
        """Initialize the sensor."""

        self._attr_unique_id = f"{entry_id}_{description.key}"
        self.entity_description = description
        self._sabnzbd_api = sabnzbd_api_data
        self._attr_name = f"{client_name} {description.name}"
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, entry_id)},
            name=DEFAULT_NAME,
        )

    async def async_added_to_hass(self):
        """Call when entity about to be added to hass."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_SABNZBD_UPDATED, self.update_state
            )
        )

    def update_state(self, args):
        """Get the latest data and updates the states."""
        self._attr_native_value = self._sabnzbd_api.get_queue_field(
            self.entity_description.key
        )

        if self._attr_native_value is not None:
            if self.entity_description.key == SPEED_KEY:
                self._attr_native_value = round(
                    float(self._attr_native_value) / 1024, 1
                )
            elif "size" in self.entity_description.key:
                self._attr_native_value = round(float(self._attr_native_value), 2)
        self.schedule_update_ha_state()
