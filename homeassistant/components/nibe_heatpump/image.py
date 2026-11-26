"""The Nibe Heat Pump heating curve images."""

from dataclasses import fields
from typing import override

from nibe.coil import Coil
from nibe.coil_groups import (
    CLIMATE_COILGROUPS,
    HEATING_CURVE_COILGROUPS,
    HeatingCurveCoilGroup,
)
from nibe.exceptions import CoilNotFoundException
from nibe.heating_curve import HeatingCurveCoilGroupData

from homeassistant.components.image import ImageEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import LOGGER
from .coordinator import CoilCoordinator, NibeHeatpumpConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: NibeHeatpumpConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up platform."""

    coordinator = config_entry.runtime_data

    def heating_curves():
        for key, group in HEATING_CURVE_COILGROUPS.get(coordinator.series, {}).items():
            try:
                yield NibeHeatingCurveImage(coordinator, key, group)
            except CoilNotFoundException as exception:
                LOGGER.debug("Skipping heating curve: %s due to %s", key, exception)

    async_add_entities(heating_curves())


class NibeHeatingCurveImage(CoordinatorEntity[CoilCoordinator], ImageEntity):
    """Heating curve of a climate system, rendered as SVG."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_content_type = "image/svg+xml"
    _attr_translation_key = "heating_curve"
    _image: bytes | None = None
    _data: HeatingCurveCoilGroupData | None = None

    def __init__(
        self,
        coordinator: CoilCoordinator,
        key: str,
        group: HeatingCurveCoilGroup,
    ) -> None:
        """Initialize entity."""
        heatpump = coordinator.heatpump
        for required in (group.curve, group.min_supply, group.max_supply):
            heatpump.get_coil_by_address(required)

        self._coils: dict[str, Coil] = {}
        for field in fields(group):
            try:
                self._coils[field.name] = heatpump.get_coil_by_address(
                    getattr(group, field.name)
                )
            except CoilNotFoundException:
                continue

        super().__init__(
            coordinator,
            {coil.address for coil in self._coils.values()},
        )
        ImageEntity.__init__(self, coordinator.hass)

        self._attr_unique_id = f"{coordinator.unique_id}-heating_curve-{key}"
        self._attr_device_info = coordinator.device_info
        self._attr_translation_placeholders = {"system": key.upper()}
        climate = CLIMATE_COILGROUPS.get(coordinator.series, {}).get(key)
        self._attr_entity_registry_enabled_default = (
            climate is not None and climate.active_accessory is None
        )

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        data = HeatingCurveCoilGroupData(
            **{
                name: self.coordinator.data.get(coil.address)
                for name, coil in self._coils.items()
            }
        )
        if data != self._data:
            self._data = data
            if (image := data.svg()) != self._image:
                self._image = image
                self._attr_image_last_updated = dt_util.utcnow() if image else None
        super()._handle_coordinator_update()

    @property
    @override
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self._image is not None

    @override
    async def async_image(self) -> bytes | None:
        """Return bytes of image."""
        return self._image
