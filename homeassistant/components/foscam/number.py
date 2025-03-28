"""Foscam number platform for Home Assistant."""

from __future__ import annotations

from coordinator import FoscamConfigEntry, FoscamCoordinator
from entity import FoscamEntity

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

VOLUME_DESCRIPTION = NumberEntityDescription(
    key="Volume",
    name="Volume Setting",
    icon="mdi:volume-source",
    native_min_value=0,
    native_max_value=100,
    native_step=1,
)

SPEAK_VOLUME_DESCRIPTION = NumberEntityDescription(
    key="SpeakVolume",
    name="SpeakVolume Setting",
    icon="mdi:account-voice",
    native_min_value=0,
    native_max_value=100,
    native_step=1,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: FoscamConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Reolink Smart AI number entities based on a config entry."""
    coordinator = config_entry.runtime_data
    await coordinator.async_config_entry_first_refresh()
    entities = [
        FoscamVolumeNumberEntity(coordinator, config_entry, VOLUME_DESCRIPTION),
        FoscamVolumeNumberEntity(coordinator, config_entry, SPEAK_VOLUME_DESCRIPTION),
    ]

    async_add_entities(entities)


class FoscamVolumeNumberEntity(FoscamEntity, NumberEntity):
    """Representation of a Reolink Smart AI number entity."""

    def __init__(
        self,
        coordinator: FoscamCoordinator,
        config_entry: FoscamConfigEntry,
        description: NumberEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, config_entry.entry_id)
        self.coordinator = coordinator
        self.entity_description = description
        self._attr_unique_id = f"{config_entry.entry_id}_{description.key}"
        self._state = self.coordinator.data.get(self.entity_description.key, False)

    @property
    def native_value(self):
        """Return the current value."""
        return self._state

    async def async_set_native_value(self, value: float) -> None:
        """Set the value."""
        if self.entity_description.key == "Volume":
            ret, _ = await self.hass.async_add_executor_job(
                getattr(self.coordinator.session, "setAudioVolume"), int(value)
            )
        elif self.entity_description.key == "SpeakVolume":
            ret, _ = await self.hass.async_add_executor_job(
                getattr(self.coordinator.session, "setSpeakVolume"), int(value)
            )

        await self.coordinator.async_request_refresh()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._state = self.coordinator.data.get(self.entity_description.key, False)
        self.async_write_ha_state()
