"""Number platform for Palazzetti settings."""

from __future__ import annotations

from pypalazzetti.exceptions import CommunicationError, ValidationError
from pypalazzetti.fan import FanType

from homeassistant.components.number import NumberDeviceClass, NumberEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import PalazzettiConfigEntry, PalazzettiDataUpdateCoordinator
from .entity import PalazzettiEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: PalazzettiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Palazzetti number platform."""

    entities: list[PalazzettiEntity] = [
        PalazzettiCombustionPowerEntity(config_entry.runtime_data)
    ]

    if config_entry.runtime_data.client.has_fan(FanType.LEFT):
        entities.append(PalazzettiFanEntity(config_entry.runtime_data, FanType.LEFT))

    if config_entry.runtime_data.client.has_fan(FanType.RIGHT):
        entities.append(PalazzettiFanEntity(config_entry.runtime_data, FanType.RIGHT))

    async_add_entities(entities)


class PalazzettiCombustionPowerEntity(PalazzettiEntity, NumberEntity):
    """Representation of Palazzetti number entity for Combustion power."""

    _attr_translation_key = "combustion_power"
    _attr_device_class = NumberDeviceClass.POWER_FACTOR
    _attr_native_min_value = 1
    _attr_native_max_value = 5
    _attr_native_step = 1

    def __init__(
        self,
        coordinator: PalazzettiDataUpdateCoordinator,
    ) -> None:
        """Initialize the Palazzetti number entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}-combustion_power"

    @property
    def native_value(self) -> float:
        """Return the state of the setting entity."""
        return self.coordinator.client.power_mode

    async def async_set_native_value(self, value: float) -> None:
        """Update the setting."""
        try:
            await self.coordinator.client.set_power_mode(int(value))
        except CommunicationError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="cannot_connect"
            ) from err
        except ValidationError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_combustion_power",
                translation_placeholders={
                    "value": str(value),
                },
            ) from err

        await self.coordinator.async_request_refresh()


class PalazzettiFanEntity(PalazzettiEntity, NumberEntity):
    """Representation of Palazzetti number entity for Combustion power."""

    _attr_device_class = NumberDeviceClass.WIND_SPEED
    _attr_native_step = 1

    def __init__(
        self, coordinator: PalazzettiDataUpdateCoordinator, fan: FanType
    ) -> None:
        """Initialize the Palazzetti number entity."""
        super().__init__(coordinator)
        self.fan = fan

        self._attr_translation_key = f"fan_{str.lower(fan.name)}_speed"
        self._attr_native_min_value = coordinator.client.min_fan_speed(fan)
        self._attr_native_max_value = coordinator.client.max_fan_speed(fan)
        self._attr_unique_id = (
            f"{coordinator.config_entry.unique_id}-fan_{str.lower(fan.name)}_speed"
        )

    @property
    def native_value(self) -> float:
        """Return the state of the setting entity."""
        return self.coordinator.client.current_fan_speed(self.fan)

    async def async_set_native_value(self, value: float) -> None:
        """Update the setting."""
        try:
            await self.coordinator.client.set_fan_speed(int(value), self.fan)
        except CommunicationError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="cannot_connect"
            ) from err
        except ValidationError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_fan_speed",
                translation_placeholders={
                    "name": str.lower(self.fan.name),
                    "value": str(value),
                },
            ) from err

        await self.coordinator.async_request_refresh()
