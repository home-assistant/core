"""The Seko Pooldose API Sensors."""

from typing import cast

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import PooldoseCoordinator
from .pooldose_api import PooldoseAPIClient

SENSOR_MAP: dict[str, tuple[str, str | None, str | None, str]] = {
    "pool_temp_ist": (
        "Pool Temperature Actual",
        "°C",
        "temperature",
        "PDPR1H1HAW100_FW539187_w_1eommf39k",
    ),
    "pool_ph_ist": ("Pool pH Actual", "pH", None, "PDPR1H1HAW100_FW539187_w_1ekeigkin"),
    "pool_ph_soll": (
        "Pool pH Target",
        "pH",
        None,
        "PDPR1H1HAW100_FW539187_w_1ekeiqfat",
    ),
    "pool_orp_ist": (
        "Pool ORP Actual",
        "mV",
        None,
        "PDPR1H1HAW100_FW539187_w_1eklenb23",
    ),
    "pool_orp_soll": (
        "Pool ORP Target",
        "mV",
        None,
        "PDPR1H1HAW100_FW539187_w_1eklgnjk2",
    ),
    "pool_zirkulation_raw": (
        "Pool Circulation Pump raw",
        None,
        None,
        "PDPR1H1HAW100_FW539187_w_1ekga097n",
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Pooldose sensors from a config entry."""
    data = hass.data["pooldose"][entry.entry_id]
    coordinator = data["coordinator"]
    api = data["api"]

    entities = []
    for uid, (name, unit, device_class, key) in SENSOR_MAP.items():
        entities.append(
            PooldoseSensor(coordinator, api, name, uid, key, unit, device_class)
        )
    async_add_entities(entities)


class PooldoseSensor(CoordinatorEntity, SensorEntity):
    """Sensor entity for Seko Pooldose API."""

    def __init__(
        self,
        coordinator: PooldoseCoordinator,
        api: PooldoseAPIClient,
        name: str,
        uid: str,
        key: str,
        unit: str | None,
        device_class: str | None,
    ) -> None:
        """Initialize a PooldoseSensor entity."""
        super().__init__(coordinator)
        self._api = api
        self._attr_name = name
        self._attr_unique_id = uid
        self._key = key
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = cast(SensorDeviceClass | None, device_class)

    @property
    def native_value(self) -> float | int | str | None:
        """Return the current value of the sensor."""
        try:
            value = self.coordinator.data["devicedata"][self._api.serial_key][
                self._key
            ]["current"]
        except (KeyError, TypeError):
            return None
        # Optionally, cast to float/int if appropriate for your sensors
        return value
