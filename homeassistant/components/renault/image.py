"""Support for Renault image entities."""

from homeassistant.components.image import ImageEntity, ImageEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import RenaultConfigEntry
from .entity import RenaultEntity
from .renault_vehicle import RenaultVehicleProxy

PARALLEL_UPDATES = 0

VEHICLE_IMAGE_DESCRIPTION = ImageEntityDescription(
    key="vehicle_image",
    translation_key="vehicle_image",
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RenaultConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Renault image entities from config entry."""
    entities = [
        RenaultImageSensor(vehicle, VEHICLE_IMAGE_DESCRIPTION)
        for vehicle in config_entry.runtime_data.vehicles.values()
        if vehicle.details.get_picture()
    ]
    async_add_entities(entities)


class RenaultImageSensor(RenaultEntity, ImageEntity):
    """Representation of a Renault vehicle image."""

    def __init__(
        self, vehicle: RenaultVehicleProxy, description: ImageEntityDescription
    ) -> None:
        """Initialize the image entity."""
        RenaultEntity.__init__(self, vehicle, description)
        ImageEntity.__init__(self, vehicle.hass)
        self._attr_image_last_updated = dt_util.utcnow()

    @property
    def image_url(self) -> str | None:
        """Return the URL for the image."""
        return self.vehicle.details.get_picture()
