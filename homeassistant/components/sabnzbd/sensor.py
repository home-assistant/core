"""Support for monitoring an SABnzbd NZB client."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import DOMAIN, SIGNAL_SABNZBD_UPDATED, SabnzbdApiData
from ...config_entries import ConfigEntry
from ...const import DATA_GIGABYTES, DATA_MEGABYTES, DATA_RATE_MEGABYTES_PER_SECOND
from ...core import HomeAssistant
from ...helpers.entity_platform import AddEntitiesCallback
from .const import KEY_API, KEY_NAME


@dataclass
class SabnzbdRequiredKeysMixin:
    """Mixin for required keys."""

    field_name: str


@dataclass
class SabnzbdSensorEntityDescription(SensorEntityDescription, SabnzbdRequiredKeysMixin):
    """Describes Sabnzbd sensor entity."""


SENSOR_TYPES: tuple[SabnzbdSensorEntityDescription, ...] = (
    SabnzbdSensorEntityDescription(
        key="current_status",
        name="Status",
        field_name="status",
    ),
    SabnzbdSensorEntityDescription(
        key="speed",
        name="Speed",
        native_unit_of_measurement=DATA_RATE_MEGABYTES_PER_SECOND,
        field_name="kbpersec",
    ),
    SabnzbdSensorEntityDescription(
        key="queue_size",
        name="Queue",
        native_unit_of_measurement=DATA_MEGABYTES,
        field_name="mb",
    ),
    SabnzbdSensorEntityDescription(
        key="queue_remaining",
        name="Left",
        native_unit_of_measurement=DATA_MEGABYTES,
        field_name="mbleft",
    ),
    SabnzbdSensorEntityDescription(
        key="disk_size",
        name="Disk",
        native_unit_of_measurement=DATA_GIGABYTES,
        field_name="diskspacetotal1",
    ),
    SabnzbdSensorEntityDescription(
        key="disk_free",
        name="Disk Free",
        native_unit_of_measurement=DATA_GIGABYTES,
        field_name="diskspace1",
    ),
    SabnzbdSensorEntityDescription(
        key="queue_count",
        name="Queue Count",
        field_name="noofslots_total",
    ),
    SabnzbdSensorEntityDescription(
        key="day_size",
        name="Daily Total",
        native_unit_of_measurement=DATA_GIGABYTES,
        field_name="day_size",
    ),
    SabnzbdSensorEntityDescription(
        key="week_size",
        name="Weekly Total",
        native_unit_of_measurement=DATA_GIGABYTES,
        field_name="week_size",
    ),
    SabnzbdSensorEntityDescription(
        key="month_size",
        name="Monthly Total",
        native_unit_of_measurement=DATA_GIGABYTES,
        field_name="month_size",
    ),
    SabnzbdSensorEntityDescription(
        key="total_size",
        name="Total",
        native_unit_of_measurement=DATA_GIGABYTES,
        field_name="total_size",
    ),
)

SENSOR_KEYS: list[str] = [desc.key for desc in SENSOR_TYPES]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a Sabnzbd sensor entry."""

    sab_api = hass.data[DOMAIN][config_entry.entry_id][KEY_API]
    client_name = hass.data[DOMAIN][config_entry.entry_id][KEY_NAME]
    sab_api_data = SabnzbdApiData(sab_api)

    async_add_entities(
        [SabnzbdSensor(sab_api_data, client_name, sensor) for sensor in SENSOR_TYPES]
    )


class SabnzbdSensor(SensorEntity):
    """Representation of an SABnzbd sensor."""

    entity_description: SabnzbdSensorEntityDescription
    _attr_should_poll = False

    def __init__(
        self, sabnzbd_api_data, client_name, description: SabnzbdSensorEntityDescription
    ):
        """Initialize the sensor."""
        self.entity_description = description
        self._sabnzbd_api = sabnzbd_api_data
        self._attr_name = f"{client_name} {description.name}"

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
            self.entity_description.field_name
        )

        if self.entity_description.key == "speed":
            self._attr_native_value = round(float(self._attr_native_value) / 1024, 1)
        elif "size" in self.entity_description.key:
            self._attr_native_value = round(float(self._attr_native_value), 2)

        self.schedule_update_ha_state()
