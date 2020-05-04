"""Support for Synology DSM Sensors."""
from typing import Dict

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONF_DISKS,
    DATA_MEGABYTES,
    DATA_RATE_KILOBYTES_PER_SECOND,
    DATA_TERABYTES,
    TEMP_CELSIUS,
)
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.util.temperature import celsius_to_fahrenheit

from . import SynoApi
from .const import (
    BASE_NAME,
    CONF_VOLUMES,
    DOMAIN,
    STORAGE_DISK_SENSORS,
    STORAGE_VOL_SENSORS,
    TEMP_SENSORS_KEYS,
    UTILISATION_SENSORS,
)

ATTRIBUTION = "Data provided by Synology"


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the Synology NAS Sensor."""

    api = hass.data[DOMAIN][entry.unique_id]

    sensors = [
        SynoNasUtilSensor(api, sensor_type, UTILISATION_SENSORS[sensor_type])
        for sensor_type in UTILISATION_SENSORS
    ]

    # Handle all volumes
    if api.storage.volumes_ids:
        for volume in entry.data.get(CONF_VOLUMES, api.storage.volumes_ids):
            sensors += [
                SynoNasStorageSensor(
                    api, sensor_type, STORAGE_VOL_SENSORS[sensor_type], volume
                )
                for sensor_type in STORAGE_VOL_SENSORS
            ]

    # Handle all disks
    if api.storage.disks_ids:
        for disk in entry.data.get(CONF_DISKS, api.storage.disks_ids):
            sensors += [
                SynoNasStorageSensor(
                    api, sensor_type, STORAGE_DISK_SENSORS[sensor_type], disk
                )
                for sensor_type in STORAGE_DISK_SENSORS
            ]

    async_add_entities(sensors)


class SynoNasSensor(Entity):
    """Representation of a Synology NAS sensor."""

    def __init__(
        self,
        api: SynoApi,
        sensor_type: str,
        sensor_info: Dict[str, str],
        monitored_device: str = None,
    ):
        """Initialize the sensor."""
        self._api = api
        self.sensor_type = sensor_type
        self._name = f"{BASE_NAME} {sensor_info[0]}"
        self._unit = sensor_info[1]
        self._icon = sensor_info[2]
        self.monitored_device = monitored_device
        self._unique_id = f"{self._api.information.serial}_{sensor_info[0]}"

        if self.monitored_device:
            self._name += f" ({self.monitored_device})"
            self._unique_id += f"_{self.monitored_device}"

        self._unsub_dispatcher = None

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._unique_id

    @property
    def name(self) -> str:
        """Return the name."""
        return self._name

    @property
    def icon(self) -> str:
        """Return the icon."""
        return self._icon

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit the value is expressed in."""
        if self.sensor_type in TEMP_SENSORS_KEYS:
            return self._api.temp_unit
        return self._unit

    @property
    def device_state_attributes(self) -> Dict[str, any]:
        """Return the state attributes."""
        return {ATTR_ATTRIBUTION: ATTRIBUTION}

    @property
    def device_info(self) -> Dict[str, any]:
        """Return the device information."""
        return {
            "identifiers": {(DOMAIN, self._api.information.serial)},
            "name": "Synology NAS",
            "manufacturer": "Synology",
            "model": self._api.information.model,
            "sw_version": self._api.information.version_string,
        }

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False

    async def async_update(self):
        """Only used by the generic entity update service."""
        await self._api.update()

    async def async_added_to_hass(self):
        """Register state update callback."""
        self._unsub_dispatcher = async_dispatcher_connect(
            self.hass, self._api.signal_sensor_update, self.async_write_ha_state
        )

    async def async_will_remove_from_hass(self):
        """Clean up after entity before removal."""
        self._unsub_dispatcher()


class SynoNasUtilSensor(SynoNasSensor):
    """Representation a Synology Utilisation sensor."""

    @property
    def state(self):
        """Return the state."""
        attr = getattr(self._api.utilisation, self.sensor_type)
        if callable(attr):
            attr = attr()
        if not attr:
            return None

        # Data (RAM)
        if self._unit == DATA_MEGABYTES:
            return round(attr / 1024.0 ** 2, 1)

        # Network
        if self._unit == DATA_RATE_KILOBYTES_PER_SECOND:
            return round(attr / 1024.0, 1)

        return attr


class SynoNasStorageSensor(SynoNasSensor):
    """Representation a Synology Storage sensor."""

    @property
    def state(self):
        """Return the state."""
        attr = getattr(self._api.storage, self.sensor_type)(self.monitored_device)
        if not attr:
            return None

        # Data (disk space)
        if self._unit == DATA_TERABYTES:
            return round(attr / 1024.0 ** 4, 2)

        # Temperature
        if self._api.temp_unit == TEMP_CELSIUS:
            # Celsius
            return attr
        if self.sensor_type in TEMP_SENSORS_KEYS:
            # Fahrenheit
            return celsius_to_fahrenheit(attr)

        return attr

    @property
    def device_info(self) -> Dict[str, any]:
        """Return the device information."""
        return {
            "identifiers": {
                (DOMAIN, self._api.information.serial, self.monitored_device)
            },
            "name": f"Synology NAS ({self.monitored_device})",
            "manufacturer": "Synology",
            "model": self._api.information.model,
            "sw_version": self._api.information.version_string,
            "via_device": (DOMAIN, self._api.information.serial),
        }
