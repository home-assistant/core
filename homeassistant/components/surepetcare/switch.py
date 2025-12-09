"""Support for Sure PetCare Flaps switches."""

from __future__ import annotations

from typing import Any, cast

from surepy.const import BASE_RESOURCE
from surepy.entities import SurepyEntity
from surepy.entities.pet import Pet as SurepyPet
from surepy.enums import EntityType
from surepy.exceptions import SurePetcareError

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, PROFILE_INDOOR, PROFILE_OUTDOOR
from .coordinator import SurePetcareDataCoordinator
from .entity import SurePetcareEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Sure PetCare switches on a config entry."""

    coordinator: SurePetcareDataCoordinator = hass.data[DOMAIN][entry.entry_id]

    pets_by_tag_id: dict[int, SurepyPet] = {}
    for entity in coordinator.data.values():
        if entity.type == EntityType.PET:
            pet = cast(SurepyPet, entity)
            if pet.tag_id is not None:
                pets_by_tag_id[pet.tag_id] = pet

    entities: list[SurePetcareIndoorModeSwitch] = []
    for entity in coordinator.data.values():
        if entity.type in [EntityType.CAT_FLAP, EntityType.PET_FLAP]:
            for tag_data in entity.raw_data().get("tags", []):
                tag_id = tag_data.get("id")
                if tag_id in pets_by_tag_id:
                    entities.append(
                        SurePetcareIndoorModeSwitch(
                            pet=pets_by_tag_id[tag_id],
                            flap=entity,
                            coordinator=coordinator,
                        )
                    )

    async_add_entities(entities)


class SurePetcareIndoorModeSwitch(SurePetcareEntity, SwitchEntity):
    """A switch implementation for Sure Petcare pet indoor mode."""

    _attr_has_entity_name = True
    _attr_translation_key = "indoor_mode"
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        pet: SurepyPet,
        flap: SurepyEntity,
        coordinator: SurePetcareDataCoordinator,
    ) -> None:
        """Initialize a Sure Petcare indoor mode switch."""
        self._pet = pet
        self._flap = flap
        self._profile_id: int | None = None
        self._available = False

        # Initialize with flap_id so the entity is attached to the flap device
        super().__init__(flap.id, coordinator)

        self._attr_unique_id = f"{self._device_id}-{pet.id}-indoor_mode"
        self._attr_translation_placeholders = {"pet_name": pet.name}

    @property
    def available(self) -> bool:
        """Return true if entity is available."""
        return self._available and super().available

    @callback
    def _update_attr(self, surepy_entity: SurepyEntity) -> None:
        """Update the state from the flap's tag data."""
        tags_by_id = {
            tag.get("id"): tag for tag in surepy_entity.raw_data().get("tags", [])
        }

        pet_tag = tags_by_id.get(self._pet.tag_id)
        if pet_tag is None:
            # Pet no longer configured for this flap
            self._available = False
            self._profile_id = None
            return

        self._available = True
        self._profile_id = pet_tag.get("profile", PROFILE_OUTDOOR)
        self._attr_is_on = self._profile_id == PROFILE_INDOOR

    async def _async_set_profile(self, profile: int) -> None:
        """Set the pet's profile on this flap."""
        try:
            await self.coordinator.surepy.sac.call(
                method="PUT",
                resource=f"{BASE_RESOURCE}/device/{self._flap.id}/tag/{self._pet.tag_id}",
                json={"profile": profile},
            )
        except SurePetcareError as err:
            await self.coordinator.async_request_refresh()
            mode = "indoor" if profile == PROFILE_INDOOR else "outdoor"
            raise HomeAssistantError(
                f"Failed to set {self._pet.name} {mode} mode on {self._flap.name}"
            ) from err

        # Update state immediately after successful API call
        self._profile_id = profile
        self._attr_is_on = profile == PROFILE_INDOOR
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch (set indoor mode)."""
        if self._attr_is_on:
            return

        await self._async_set_profile(PROFILE_INDOOR)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch (set outdoor mode)."""
        if not self._attr_is_on:
            return

        await self._async_set_profile(PROFILE_OUTDOOR)
