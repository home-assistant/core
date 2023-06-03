"""Support for EZVIZ number controls."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging

from pyezviz.constants import DeviceCatagories, SupportExt
from pyezviz.exceptions import (
    EzvizAuthTokenExpired,
    EzvizAuthVerificationCode,
    HTTPError,
    InvalidURL,
    PyEzvizError,
)

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import EzvizDataUpdateCoordinator
from .entity import EzvizBaseEntity

SCAN_INTERVAL = timedelta(seconds=3600)
PARALLEL_UPDATES = 0
_LOGGER = logging.getLogger(__name__)


@dataclass
class EzvizNumberEntityDescriptionMixin:
    """Mixin values for EZVIZ Number entities."""

    supported_ext: str


@dataclass
class EzvizNumberEntityDescription(
    NumberEntityDescription, EzvizNumberEntityDescriptionMixin
):
    """Describe a EZVIZ Number."""


NUMBER_TYPES = EzvizNumberEntityDescription(
    key="detection_sensibility",
    name="Detection sensitivity",
    icon="mdi:eye",
    entity_category=EntityCategory.CONFIG,
    native_min_value=0,
    native_step=1,
    supported_ext=str(SupportExt.SupportSensibilityAdjust.value),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up EZVIZ sensors based on a config entry."""
    coordinator: EzvizDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]

    async_add_entities(
        [
            EzvizSensor(coordinator, camera, NUMBER_TYPES)
            for camera in coordinator.data
            for capibility, value in coordinator.data[camera]["supportExt"].items()
            if capibility == NUMBER_TYPES.supported_ext
            if value == "1"
        ],
        update_before_add=True,
    )


class EzvizSensor(EzvizBaseEntity, NumberEntity):
    """Representation of a EZVIZ number entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: EzvizDataUpdateCoordinator,
        serial: str,
        description: EzvizNumberEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, serial)
        self.battery_cam_type = bool(
            self.data["device_category"]
            == DeviceCatagories.BATTERY_CAMERA_DEVICE_CATEGORY.value
        )
        self._attr_unique_id = f"{serial}_{description.key}"
        self._attr_native_max_value = 100 if self.battery_cam_type else 6
        self.entity_description = description
        self.sensor_value: int | None = None

    @property
    def native_value(self) -> float | None:
        """Return the state of the entity."""
        if self.sensor_value is not None:
            return float(self.sensor_value)
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

        self.sensor_value = level

    def update(self) -> None:
        """Fetch data from EZVIZ."""
        _LOGGER.debug("Updating %s", self.name)
        try:
            if self.battery_cam_type:
                self.sensor_value = (
                    self.coordinator.ezviz_client.get_detection_sensibility(
                        self._serial,
                        "3",
                    )
                )
            else:
                self.sensor_value = (
                    self.coordinator.ezviz_client.get_detection_sensibility(
                        self._serial,
                    )
                )

        except (EzvizAuthTokenExpired, EzvizAuthVerificationCode) as error:
            raise ConfigEntryAuthFailed from error

        except (InvalidURL, HTTPError, PyEzvizError) as error:
            raise HomeAssistantError(f"Invalid response from API: {error}") from error
