"""Support for EZVIZ number controls."""
from __future__ import annotations

from pyezviz.constants import DeviceCatagories
from pyezviz.exceptions import HTTPError, PyEzvizError

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import EzvizDataUpdateCoordinator
from .entity import EzvizEntity

PARALLEL_UPDATES = 1

NUMBER_TYPES = NumberEntityDescription(
    key="detection_sensibility",
    name="Detection sensitivity",
    icon="mdi:eye",
    entity_category=EntityCategory.CONFIG,
    native_min_value=0,
    native_step=1,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up EZVIZ sensors based on a config entry."""
    coordinator: EzvizDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]

    async_add_entities(
        EzvizSensor(coordinator, camera, sensor, NUMBER_TYPES)
        for camera in coordinator.data
        for sensor, value in coordinator.data[camera].items()
        if sensor in NUMBER_TYPES.key
        if value
    )


class EzvizSensor(EzvizEntity, NumberEntity):
    """Representation of a EZVIZ number entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: EzvizDataUpdateCoordinator,
        serial: str,
        sensor: str,
        description: NumberEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, serial)
        self._sensor_name = sensor
        self.battery_cam_type = bool(
            self.data["device_category"]
            == DeviceCatagories.BATTERY_CAMERA_DEVICE_CATEGORY.value
        )
        self._attr_unique_id = f"{serial}_{sensor}"
        self._attr_native_max_value = 100 if self.battery_cam_type else 6
        self.entity_description = description

    @property
    def native_value(self) -> float | None:
        """Return the state of the entity."""
        try:
            return float(self.data[self._sensor_name])
        except ValueError:
            return None

    def set_native_value(self, value: float) -> None:
        """Set camera detection sensitivity."""
        level = int(value)
        try:
            if self.battery_cam_type:
                self.coordinator.ezviz_client.detection_sensibility(
                    self._serial,
                    level,
                    3,
                )
            else:
                self.coordinator.ezviz_client.detection_sensibility(
                    self._serial,
                    level,
                    0,
                )

        except (HTTPError, PyEzvizError) as err:
            raise HomeAssistantError(
                f"Cannot set detection sensitivity level on {self.name}"
            ) from err
