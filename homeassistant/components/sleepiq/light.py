"""Support for controlling SleepNumber foundation lights."""

from homeassistant.components.light import LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DATA_SLEEPIQ, SleepIQDataUpdateCoordinator, SleepIQEntity
from .const import LIGHT, LIGHTS, NAME, RIGHT, UNDER_BED_LIGHT_ID


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the SleepIQ light entities."""
    coordinator = hass.data[DATA_SLEEPIQ].coordinators[config_entry.data[CONF_USERNAME]]
    entities = []

    for bed_id in coordinator.data:
        foundation_features = await hass.async_add_executor_job(
            coordinator.client.foundation_features, bed_id
        )

        if foundation_features.hasUnderbedLight:
            entities.append(SleepIQLight(coordinator, bed_id, UNDER_BED_LIGHT_ID))

    async_add_entities(entities, True)


class SleepIQLight(SleepIQEntity, LightEntity):
    """Implementation of a SleepIQ light entity."""

    def __init__(
        self, coordinator: SleepIQDataUpdateCoordinator, bed_id: str, light_id: int
    ) -> None:
        """Initialize the SleepIQ light entity."""
        super().__init__(coordinator, bed_id, RIGHT)
        self._client = coordinator.client
        self._light_id = light_id
        self._light_on = bool(coordinator.data[self.bed_id][LIGHT].setting)

    @callback
    def _update_callback(self):
        """Call update method."""
        self._light_on = bool(self.coordinator.data[self.bed_id][LIGHT].setting)
        self.async_write_ha_state()

    @property
    def unique_id(self) -> str:
        """Return unique ID for the entity."""
        return f"{self.bed_id}_{LIGHT}_{self._light_id}"

    @property
    def name(self) -> str:
        """Return name for the entity."""
        return f"{NAME} {self._bed.name} {LIGHTS[self._light_id]}"

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        return self._light_on

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the light on."""
        await self.hass.async_add_executor_job(self._set_light, True)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the light off."""
        await self.hass.async_add_executor_job(self._set_light, False)

    def _set_light(self, new_state):
        """Update light state and cause Home Assistant to correctly update."""
        self._client.set_light(self._light_id, new_state, self.bed_id)
        self._light_on = new_state
        self.async_write_ha_state()
