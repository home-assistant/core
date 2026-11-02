"""Control for steamer."""

import logging
from typing import override

from huum.const import SaunaStatus
from huum.exceptions import HuumError, SafetyException

from homeassistant.components.number import NumberDeviceClass, NumberEntity
from homeassistant.const import UnitOfRatio
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONFIG_STEAMER, CONFIG_STEAMER_AND_LIGHT, DOMAIN
from .coordinator import HuumConfigEntry, HuumDataUpdateCoordinator
from .entity import HuumBaseEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HuumConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up steamer if applicable."""
    coordinator = config_entry.runtime_data

    # Light is configured for this sauna.
    if coordinator.data.config in [CONFIG_STEAMER, CONFIG_STEAMER_AND_LIGHT]:
        async_add_entities([HuumSteamer(coordinator)])


class HuumSteamer(HuumBaseEntity, NumberEntity):
    """Representation of a steamer."""

    _attr_translation_key = "humidity"
    _attr_device_class = NumberDeviceClass.HUMIDITY
    _attr_native_unit_of_measurement = UnitOfRatio.PERCENTAGE
    _attr_native_max_value = 40
    _attr_native_min_value = 0
    _attr_native_step = 1

    def __init__(self, coordinator: HuumDataUpdateCoordinator) -> None:
        """Initialize the steamer."""
        super().__init__(coordinator)

        self._attr_unique_id = coordinator.config_entry.entry_id

    @property
    @override
    def native_value(self) -> float | None:
        """Return the current value."""
        return self.coordinator.data.humidity

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        target_temperature = self.coordinator.data.target_temperature
        if (
            not target_temperature
            or self.coordinator.data.status != SaunaStatus.ONLINE_HEATING
        ):
            return

        try:
            await self.coordinator.huum.turn_on(
                temperature=target_temperature, humidity=int(value)
            )
        except SafetyException as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="unable_to_turn_on",
            ) from err
        except HuumError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="communication_error",
            ) from err
        await self.coordinator.async_refresh()
