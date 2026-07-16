"""Radar configuration numbers for LinknLink eMotion Ultra."""

from typing import override

from aiolinknlink import UltraError

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import EntityCategory, UnitOfLength, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import LinknLinkConfigEntry
from .entity import LinknLinkEntity

PARALLEL_UPDATES = 1

MAX_ABSENCE_DELAY = 18 * 60 * 60

RADAR_NUMBER_DESCRIPTIONS: tuple[NumberEntityDescription, ...] = (
    NumberEntityDescription(
        key="radar_height",
        translation_key="radar_height",
        entity_category=EntityCategory.CONFIG,
        device_class=NumberDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.CENTIMETERS,
        native_min_value=0,
        native_max_value=1000,
        native_step=1,
        mode=NumberMode.BOX,
    ),
    NumberEntityDescription(
        key="radar_z_minimum",
        translation_key="radar_z_minimum",
        entity_category=EntityCategory.CONFIG,
        device_class=NumberDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.METERS,
        native_min_value=-6,
        native_max_value=6,
        native_step=0.1,
        mode=NumberMode.BOX,
    ),
    NumberEntityDescription(
        key="radar_z_maximum",
        translation_key="radar_z_maximum",
        entity_category=EntityCategory.CONFIG,
        device_class=NumberDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.METERS,
        native_min_value=-6,
        native_max_value=6,
        native_step=0.1,
        mode=NumberMode.BOX,
    ),
    NumberEntityDescription(
        key="radar_default_absence_delay",
        translation_key="radar_default_absence_delay",
        entity_category=EntityCategory.CONFIG,
        device_class=NumberDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        native_min_value=0,
        native_max_value=MAX_ABSENCE_DELAY,
        native_step=1,
        mode=NumberMode.BOX,
    ),
    *(
        NumberEntityDescription(
            key=f"radar_zone_{zone}_absence_delay",
            translation_key=f"radar_zone_{zone}_absence_delay",
            entity_category=EntityCategory.CONFIG,
            device_class=NumberDeviceClass.DURATION,
            native_unit_of_measurement=UnitOfTime.SECONDS,
            native_min_value=0,
            native_max_value=MAX_ABSENCE_DELAY,
            native_step=1,
            mode=NumberMode.BOX,
        )
        for zone in range(1, 5)
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LinknLinkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up device-verified radar configuration numbers."""
    async_add_entities(
        LinknLinkRadarNumber(entry.runtime_data, description)
        for description in RADAR_NUMBER_DESCRIPTIONS
    )


class LinknLinkRadarNumber(LinknLinkEntity, NumberEntity):
    """Configure one Ultra radar number with a device read-back."""

    entity_description: NumberEntityDescription

    @property
    @override
    def available(self) -> bool:
        """Return whether this radar configuration field is readable."""
        position_state = self.coordinator.position_state
        return (
            position_state is not None
            and position_state.subscribed
            and self.native_value is not None
        )

    @property
    @override
    def native_value(self) -> float | None:
        """Return the device-read radar configuration value."""
        status = self.coordinator.radar_status
        if status is None:
            return None
        key = self.entity_description.key
        if key == "radar_height":
            return status.height
        if key == "radar_z_minimum":
            return status.z_range.minimum if status.z_range is not None else None
        if key == "radar_z_maximum":
            return status.z_range.maximum if status.z_range is not None else None
        if key == "radar_default_absence_delay":
            return status.default_absence_delay
        if key.startswith("radar_zone_"):
            zone = int(key.removeprefix("radar_zone_").removesuffix("_absence_delay"))
            return status.zone_absence_delays[zone - 1]
        return None

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set a radar number and require a matching device read-back."""
        try:
            await self._async_set_value(value)
        except (OSError, UltraError, ValueError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="control_error",
                translation_placeholders={"error": str(err) or type(err).__name__},
            ) from err

    async def _async_set_value(self, value: float) -> None:
        """Dispatch a validated number to the matching coordinator operation."""
        key = self.entity_description.key
        if key == "radar_height":
            await self.coordinator.async_set_radar_height(_as_int(value))
            return
        if key in {"radar_z_minimum", "radar_z_maximum"}:
            status = self.coordinator.radar_status
            if status is None or status.z_range is None:
                raise ValueError("Z-axis range is unavailable")
            minimum = value if key == "radar_z_minimum" else status.z_range.minimum
            maximum = value if key == "radar_z_maximum" else status.z_range.maximum
            await self.coordinator.async_set_radar_z_range(minimum, maximum)
            return
        if key == "radar_default_absence_delay":
            await self.coordinator.async_set_radar_default_absence_delay(_as_int(value))
            return
        if key.startswith("radar_zone_"):
            zone = int(key.removeprefix("radar_zone_").removesuffix("_absence_delay"))
            await self.coordinator.async_set_radar_zone_absence_delay(
                zone, _as_int(value)
            )
            return
        raise ValueError(key)

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe to radar configuration changes."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_config_listener(self._async_handle_config_update)
        )

    @callback
    def _async_handle_config_update(self) -> None:
        """Write a device-read radar configuration update."""
        self.async_write_ha_state()


def _as_int(value: float) -> int:
    """Return an integer number value without silently truncating it."""
    integer = int(value)
    if value != integer:
        raise ValueError("value must be a whole number")
    return integer
