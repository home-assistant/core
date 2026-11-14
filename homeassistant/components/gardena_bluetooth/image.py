"""Support for image entities."""

from dataclasses import dataclass, field
from typing import Any, override

from gardena_bluetooth.const import (
    AquaContour,
    AquaContourContours,
    AquaContourPosition,
    AquaContourWateringMode,
    Spray,
)
from gardena_bluetooth.parse import CharacteristicContourPoints, ContourPoints
from gardena_bluetooth.utils import contour_to_svg

from homeassistant.components.image import ImageEntity, ImageEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import GardenaBluetoothConfigEntry, GardenaBluetoothCoordinator
from .entity import GardenaBluetoothDescriptorEntity, GardenaBluetoothEntity

CONTOURS: dict[int, CharacteristicContourPoints] = {
    AquaContourWateringMode.CONTOUR_1: AquaContourContours.contour_points_1,
    AquaContourWateringMode.CONTOUR_2: AquaContourContours.contour_points_2,
    AquaContourWateringMode.CONTOUR_3: AquaContourContours.contour_points_3,
    AquaContourWateringMode.CONTOUR_4: AquaContourContours.contour_points_4,
    AquaContourWateringMode.CONTOUR_5: AquaContourContours.contour_points_5,
}


@dataclass(frozen=True, kw_only=True)
class GardenaBluetoothImageEntityDescription(ImageEntityDescription):
    """Description of entity."""

    key: str = field(init=False)
    translation_key: str = field(init=False, default="contour")
    char: CharacteristicContourPoints
    contour: int

    def __post_init__(self):
        """Initialize calculated fields."""
        object.__setattr__(self, "key", self.char.unique_id)


DESCRIPTIONS = tuple(
    GardenaBluetoothImageEntityDescription(
        char=char,
        contour=contour,
        entity_category=EntityCategory.DIAGNOSTIC,
    )
    for contour, char in CONTOURS.items()
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GardenaBluetoothConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up image based on a config entry."""
    coordinator = entry.runtime_data
    entities: list[ImageEntity] = [
        GardenaBluetoothContourImage(coordinator, description)
        for description in DESCRIPTIONS
        if description.char.unique_id in coordinator.characteristics
    ]
    if GardenaBluetoothActiveContourImage.characteristics.issubset(
        coordinator.characteristics
    ):
        entities.append(GardenaBluetoothActiveContourImage(coordinator))
    async_add_entities(entities)


class GardenaBluetoothImage(GardenaBluetoothEntity, ImageEntity):
    """Base for an image rendered from cached contour data."""

    _attr_content_type = "image/svg+xml"
    _image: bytes | None = None

    def __init__(
        self, coordinator: GardenaBluetoothCoordinator, context: Any = None
    ) -> None:
        """Initialize the image."""
        super().__init__(coordinator, context)
        # The coordinator entity does not chain its init, so image setup is missed.
        ImageEntity.__init__(self, coordinator.hass)

    def _render(self) -> bytes | None:
        """Render the current image."""
        raise NotImplementedError

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        if (image := self._render()) != self._image:
            self._image = image
            self._attr_image_last_updated = dt_util.utcnow() if image else None
        super()._handle_coordinator_update()

    @property
    @override
    def entity_picture(self) -> str | None:
        """Return a link to the image, or none while there is nothing to show."""
        if self._image is None:
            return None
        return super().entity_picture

    @override
    async def async_image(self) -> bytes | None:
        """Return bytes of image."""
        return self._image


class GardenaBluetoothContourImage(
    GardenaBluetoothDescriptorEntity, GardenaBluetoothImage
):
    """Representation of a taught contour as a map."""

    entity_description: GardenaBluetoothImageEntityDescription

    def __init__(
        self,
        coordinator: GardenaBluetoothCoordinator,
        description: GardenaBluetoothImageEntityDescription,
    ) -> None:
        """Initialize the contour image."""
        super().__init__(coordinator, description, {description.char.unique_id})
        self._attr_translation_placeholders = {"number": str(description.contour)}

    @override
    def _render(self) -> bytes | None:
        return contour_to_svg(self.coordinator.get_cached(self.entity_description.char))


class GardenaBluetoothActiveContourImage(GardenaBluetoothImage):
    """Representation of the contour in use, with the current spray drawn in."""

    _attr_translation_key = "active_contour"

    characteristics = {
        AquaContour.active_contour.unique_id,
        AquaContourPosition.active_position.unique_id,
        Spray.current_sector.unique_id,
        Spray.current_distance.unique_id,
        *(char.unique_id for char in CONTOURS.values()),
    }

    def __init__(self, coordinator: GardenaBluetoothCoordinator) -> None:
        """Initialize the active contour image."""
        super().__init__(coordinator, self.characteristics)
        self._attr_unique_id = f"{coordinator.address}-active_contour"

    def _active_points(self) -> ContourPoints | None:
        """Points of the contour assigned to the position the sprinkler is at."""
        position = self.coordinator.get_cached(AquaContourPosition.active_position)
        assigned = self.coordinator.get_cached(AquaContour.active_contour) or []
        if position is None or position < 1 or position > len(assigned):
            return None
        if (char := CONTOURS.get(assigned[position - 1])) is None:
            return None
        return self.coordinator.get_cached(char)

    def _spray(self) -> tuple[int, int] | None:
        """Angle and distance the sprinkler is currently throwing at."""
        angle = self.coordinator.get_cached(Spray.current_sector)
        distance = self.coordinator.get_cached(Spray.current_distance)
        if angle is None or not distance:
            return None
        return angle, distance

    @override
    def _render(self) -> bytes | None:
        return contour_to_svg(self._active_points(), self._spray())
