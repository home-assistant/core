"""Base entity for Habitica."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from habiticalib import ContentData, UserData
from yarl import URL

from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import CONF_URL
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, NAME
from .coordinator import (
    HabiticaConfigEntry,
    HabiticaDataUpdateCoordinator,
    HabiticaPartyCoordinator,
)


class HabiticaBase(CoordinatorEntity[HabiticaDataUpdateCoordinator]):
    """Base Habitica entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HabiticaDataUpdateCoordinator,
        entity_description: EntityDescription,
        subentry: ConfigSubentry | None = None,
    ) -> None:
        """Initialize a Habitica entity."""
        super().__init__(coordinator)
        if TYPE_CHECKING:
            assert coordinator.config_entry.unique_id
            assert self.user
        self.entity_description = entity_description
        self.subentry = subentry
        unique_id = (
            subentry.unique_id
            if subentry is not None and subentry.unique_id
            else coordinator.config_entry.unique_id
        )

        self._attr_unique_id = f"{unique_id}_{entity_description.key}"
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            manufacturer=MANUFACTURER,
            model=NAME,
            name=self.user.profile.name,
            configuration_url=(
                URL(coordinator.config_entry.data[CONF_URL]) / "profile" / unique_id
            ),
            identifiers={(DOMAIN, unique_id)},
        )

        if subentry:
            self._attr_device_info.update(
                DeviceInfo(
                    via_device=(
                        (
                            DOMAIN,
                            f"{coordinator.config_entry.unique_id}_{self.user.party.id!s}",
                        )
                    )
                )
            )

    @property
    def user(self) -> UserData | None:
        """Return the user data."""
        return self.coordinator.data.user


class HabiticaPartyMemberBase(HabiticaBase):
    """Base Habitica party member entity."""

    def __init__(
        self,
        coordinator: HabiticaDataUpdateCoordinator,
        party_coordinator: HabiticaPartyCoordinator,
        entity_description: EntityDescription,
        subentry: ConfigSubentry | None = None,
    ) -> None:
        """Initialize a Habitica entity."""
        self.party_coordinator = party_coordinator
        super().__init__(coordinator, entity_description, subentry)

    @property
    def user(self) -> UserData | None:
        """Return the user data of the party member."""
        if TYPE_CHECKING:
            assert self.subentry
            assert self.subentry.unique_id
        return self.party_coordinator.data.members.get(UUID(self.subentry.unique_id))

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        if TYPE_CHECKING:
            assert self.subentry
            assert self.subentry.unique_id
        return (
            super().available
            and UUID(self.subentry.unique_id) in self.party_coordinator.data.members
        )

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.party_coordinator.async_add_listener(self._handle_coordinator_update)
        )


class HabiticaPartyBase(CoordinatorEntity[HabiticaPartyCoordinator]):
    """Base Habitica entity representing a party."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HabiticaPartyCoordinator,
        config_entry: HabiticaConfigEntry,
        entity_description: EntityDescription,
        content: ContentData,
    ) -> None:
        """Initialize a Habitica party entity."""
        super().__init__(coordinator)
        if TYPE_CHECKING:
            assert config_entry.unique_id
        unique_id = f"{config_entry.unique_id}_{coordinator.data.party.id!s}"
        self.entity_description = entity_description
        self._attr_unique_id = f"{unique_id}_{entity_description.key}"
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            manufacturer=MANUFACTURER,
            model=NAME,
            name=coordinator.data.party.summary,
            identifiers={(DOMAIN, unique_id)},
            via_device=(DOMAIN, config_entry.unique_id),
        )
        self.content = content
