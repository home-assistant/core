"""Base class for Mastodon entities."""

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import MastodonConfigEntry
from .const import DEFAULT_NAME, DOMAIN, INSTANCE_VERSION
from .coordinator import MastodonCoordinator
from .utils import construct_mastodon_username


class MastodonEntity(CoordinatorEntity[MastodonCoordinator]):
    """Defines a base Mastodon entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MastodonCoordinator,
        entity_description: EntityDescription,
        data: MastodonConfigEntry,
    ) -> None:
        """Initialize Mastodon entity."""
        super().__init__(coordinator)
        unique_id = data.unique_id
        assert unique_id is not None
        self._attr_unique_id = f"{unique_id}_{entity_description.key}"

        # Legacy yaml config default title is Mastodon, don't make name Mastodon Mastodon
        name = "Mastodon"
        if data.title != DEFAULT_NAME:
            name = f"Mastodon {data.title}"

        full_account_name = construct_mastodon_username(
            data.runtime_data.instance, data.runtime_data.account
        )

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            manufacturer="Mastodon gGmbH",
            model=full_account_name,
            entry_type=DeviceEntryType.SERVICE,
            sw_version=data.runtime_data.instance[INSTANCE_VERSION],
            name=name,
        )

        self.entity_description = entity_description
