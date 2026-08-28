"""Image entity for Home Connect."""

from typing import override

from aiohomeconnect.model.error import HomeConnectError

from homeassistant.components.image import Image, ImageEntity, ImageEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .common import setup_home_connect_entry
from .const import DOMAIN
from .coordinator import HomeConnectApplianceCoordinator, HomeConnectConfigEntry
from .utils import get_dict_from_home_connect_error

PARALLEL_UPDATES = 1

IMAGES = (
    ImageEntityDescription(
        key="Refrigeration.Common.EnumType.Compartment.Type.InteriorRightRC",
        translation_key="interior_right_camera",
    ),
    ImageEntityDescription(
        key="Refrigeration.Common.EnumType.Compartment.Type.DoorRightRC",
        translation_key="door_right_camera",
    ),
)


def _get_entities_for_appliance(
    appliance_coordinator: HomeConnectApplianceCoordinator,
) -> list[HomeConnectImageEntity]:
    """Get all entities for an appliance."""
    return [
        HomeConnectImageEntity(appliance_coordinator, desc)
        for desc in IMAGES
        if desc.key in appliance_coordinator.data.images
    ]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HomeConnectConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Home Connect sensor."""
    setup_home_connect_entry(
        hass,
        entry,
        _get_entities_for_appliance,
        async_add_entities,
    )


class HomeConnectImageEntity(ImageEntity):
    """Image class for Home Connect."""

    _attr_has_entity_name = True
    _last_image_key_fetched: str | None = None

    def __init__(
        self,
        appliance_coordinator: HomeConnectApplianceCoordinator,
        desc: ImageEntityDescription,
    ) -> None:
        """Initialize the entity."""
        appliance_ha_id = appliance_coordinator.data.info.ha_id
        super().__init__(appliance_coordinator.hass)
        self.appliance = appliance_coordinator.data
        self.entity_description = desc
        self.appliance_coordinator = appliance_coordinator
        self._attr_unique_id = f"{appliance_ha_id}-{desc.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, appliance_ha_id)},
        )

    @override
    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        await self.async_fetch_image()
        self.async_on_remove(
            self.appliance_coordinator.add_image_listener(
                self.entity_description.key, self._handle_coordinator_update
            )
        )

    async def async_update(self) -> None:
        """Set the value of the image based on the given value."""
        await self.appliance_coordinator.update_images()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.hass.async_create_task(self.async_fetch_image())

    async def async_fetch_image(self) -> None:
        """Fetch the image from the Home Connect API if it has changed since the last fetch."""
        image_info = self.appliance_coordinator.data.images[self.entity_description.key]
        if image_info.image_key == self._last_image_key_fetched:
            return
        self._last_image_key_fetched = image_info.image_key
        self._attr_image_last_updated = dt_util.utc_from_timestamp(
            # It is not specified whether the timestamp is in seconds or milliseconds,
            # so we check if it is larger than 10^10 (which would indicate milliseconds)
            # and convert it to seconds if necessary.
            image_info.timestamp / 1000
            if image_info.timestamp > 10_000_000_000
            else image_info.timestamp
        )
        try:
            image_data = await self.appliance_coordinator.client.get_image(
                self.appliance.info.ha_id, image_key=image_info.image_key
            )
        except HomeConnectError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="fetch_image_error",
                translation_placeholders=get_dict_from_home_connect_error(err),
            ) from err

        self._cached_image = Image(
            content_type="image/jpeg",
            content=image_data,
        )
        self.async_write_ha_state()
