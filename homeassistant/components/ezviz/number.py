"""Support for EZVIZ number controls."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging

from pyezvizapi.constants import SupportExt
from pyezvizapi.exceptions import (
    EzvizAuthTokenExpired,
    EzvizAuthVerificationCode,
    HTTPError,
    InvalidURL,
    PyEzvizError,
)

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import EzvizConfigEntry, EzvizDataUpdateCoordinator
from .entity import EzvizBaseEntity

SCAN_INTERVAL = timedelta(seconds=3600)
PARALLEL_UPDATES = 0
_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class EzvizNumberEntityDescription(NumberEntityDescription):
    """Describe a EZVIZ Number."""

    supported_ext: str
    supported_ext_value: list


NUMBER_TYPE = EzvizNumberEntityDescription(
    key="detection_sensibility",
    translation_key="detection_sensibility",
    entity_category=EntityCategory.CONFIG,
    native_min_value=0,
    native_step=1,
    supported_ext=str(SupportExt.SupportSensibilityAdjust.value),
    supported_ext_value=["1", "3"],
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EzvizConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up EZVIZ sensors based on a config entry."""
    coordinator = entry.runtime_data

    async_add_entities(
        EzvizNumber(coordinator, camera, value, entry.entry_id)
        for camera in coordinator.data
        for capability, value in coordinator.data[camera]["supportExt"].items()
        if capability == NUMBER_TYPE.supported_ext
        if value in NUMBER_TYPE.supported_ext_value
    )


class EzvizNumber(EzvizBaseEntity, NumberEntity):
    """Representation of a EZVIZ number entity."""

    def __init__(
        self,
        coordinator: EzvizDataUpdateCoordinator,
        serial: str,
        value: str,
        config_entry_id: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, serial)
        self.sensitivity_type = 3 if value == "3" else 0
        self._attr_native_max_value = 100 if value == "3" else 6
        self._attr_unique_id = f"{serial}_{NUMBER_TYPE.key}"
        self.entity_description = NUMBER_TYPE
        self.config_entry_id = config_entry_id
        self.sensor_value: int | None = None

    async def async_added_to_hass(self) -> None:
        """Run when about to be added to hass."""
        self.async_schedule_update_ha_state(True)

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
            self.coordinator.ezviz_client.detection_sensibility(
                self._serial,
                level,
                self.sensitivity_type,
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
            self.sensor_value = self.coordinator.ezviz_client.get_detection_sensibility(
                self._serial,
                str(self.sensitivity_type),
            )

        except (EzvizAuthTokenExpired, EzvizAuthVerificationCode):
            _LOGGER.debug("Failed to login to EZVIZ API")
            self.hass.async_create_task(
                self.hass.config_entries.async_reload(self.config_entry_id)
            )
            return

        except (InvalidURL, HTTPError, PyEzvizError) as error:
            raise HomeAssistantError(f"Invalid response from API: {error}") from error
