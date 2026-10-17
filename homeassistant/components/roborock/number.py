"""Support for Roborock number."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
import logging
from typing import Any, override

from roborock.devices.traits.b01 import Q10PropertiesApi
from roborock.devices.traits.b01.q10 import SoundVolumeTrait
from roborock.devices.traits.v1 import PropertiesApi
from roborock.exceptions import RoborockException
from roborock.roborock_message import RoborockZeoProtocol

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import (
    RoborockB01Q10UpdateCoordinator,
    RoborockConfigEntry,
    RoborockCoordinatorType,
    RoborockDataUpdateCoordinator,
    RoborockWashingMachineUpdateCoordinator,
)
from .entity import (
    RoborockCoordinatedEntityA01,
    RoborockCoordinatedEntityB01Q10,
    RoborockEntityV1,
)

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class RoborockNumberDescription(NumberEntityDescription):
    """Class to describe a Roborock number entity."""

    trait: Callable[[PropertiesApi], Any | None]
    """Function to determine if number entity is supported by the device."""

    get_value: Callable[[Any], float | None]
    """Function to get the value from the trait."""

    set_value: Callable[[Any, float], Coroutine[Any, Any, None]]
    """Function to set the value on the trait."""


NUMBER_DESCRIPTIONS: list[RoborockNumberDescription] = [
    RoborockNumberDescription(
        key="volume",
        translation_key="volume",
        native_min_value=0,
        native_max_value=100,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.CONFIG,
        trait=lambda api: api.sound_volume,
        get_value=lambda trait: (
            float(trait.volume) if trait.volume is not None else None
        ),
        set_value=lambda trait, value: trait.set_volume(int(value)),
    )
]


@dataclass(frozen=True, kw_only=True)
class RoborockNumberDescriptionQ10(NumberEntityDescription):
    """Class to describe a Roborock Q10 number entity."""

    trait: Callable[[Q10PropertiesApi], SoundVolumeTrait | None]
    """Function to get the trait backing the entity, if supported."""

    get_value: Callable[[SoundVolumeTrait], float | None]
    """Function to get the value from the trait."""

    set_value: Callable[[SoundVolumeTrait, float], Coroutine[Any, Any, None]]
    """Function to set the value on the trait."""


Q10_NUMBER_DESCRIPTIONS: list[RoborockNumberDescriptionQ10] = [
    RoborockNumberDescriptionQ10(
        key="volume",
        translation_key="volume",
        native_min_value=0,
        native_max_value=100,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.CONFIG,
        trait=lambda api: api.volume,
        get_value=lambda trait: (
            float(trait.volume) if trait.volume is not None else None
        ),
        set_value=lambda trait, value: trait.set_volume(int(value)),
    )
]


@dataclass(frozen=True, kw_only=True)
class RoborockNumberDescriptionA01(NumberEntityDescription):
    """Class to describe a Roborock A01 number entity."""

    data_protocol: RoborockZeoProtocol
    """The protocol that the number entity will send to the API."""


A01_NUMBER_DESCRIPTIONS: list[RoborockNumberDescriptionA01] = [
    RoborockNumberDescriptionA01(
        key="zeo_delay_start",
        translation_key="zeo_delay_start",
        data_protocol=RoborockZeoProtocol.COUNTDOWN,
        device_class=NumberDeviceClass.DURATION,
        native_min_value=0,
        native_max_value=1440,
        native_step=30,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        icon="mdi:timer-outline",
    )
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RoborockConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Roborock number platform."""
    coordinators = config_entry.runtime_data

    @callback
    def async_add_coordinator_entities(
        coordinator: RoborockCoordinatorType,
    ) -> None:
        """Add entities for a specific coordinator."""
        entities: list[NumberEntity] = []
        if isinstance(coordinator, RoborockDataUpdateCoordinator):
            entities.extend(
                RoborockNumberEntity(
                    f"{description.key}_{coordinator.duid_slug}",
                    coordinator=coordinator,
                    entity_description=description,
                    trait=trait,
                )
                for description in NUMBER_DESCRIPTIONS
                if (trait := description.trait(coordinator.properties_api)) is not None
            )
        elif isinstance(coordinator, RoborockB01Q10UpdateCoordinator):
            entities.extend(
                RoborockNumberEntityQ10(
                    f"{description.key}_{coordinator.duid_slug}",
                    coordinator=coordinator,
                    entity_description=description,
                    trait=q10_trait,
                )
                for description in Q10_NUMBER_DESCRIPTIONS
                if (q10_trait := description.trait(coordinator.api)) is not None
            )
        elif isinstance(coordinator, RoborockWashingMachineUpdateCoordinator):
            entities.extend(
                RoborockNumberEntityA01(coordinator, description)
                for description in A01_NUMBER_DESCRIPTIONS
                if description.data_protocol in coordinator.request_protocols
            )
        async_add_entities(entities)

    for coordinator in coordinators.values():
        async_add_coordinator_entities(coordinator)

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            f"roborock_coordinator_added_{config_entry.entry_id}",
            async_add_coordinator_entities,
        )
    )


class RoborockNumberEntity(RoborockEntityV1, NumberEntity):
    """A class to set options on a Roborock vacuum with fixed options."""

    entity_description: RoborockNumberDescription

    def __init__(
        self,
        unique_id: str,
        coordinator: RoborockDataUpdateCoordinator,
        entity_description: RoborockNumberDescription,
        trait: Any,
    ) -> None:
        """Create a number entity."""
        self.entity_description = entity_description
        super().__init__(
            unique_id, coordinator.device_info, api=coordinator.properties_api.command
        )
        self._trait = trait

    @property
    @override
    def native_value(self) -> float | None:
        """Get native value."""
        return self.entity_description.get_value(self._trait)

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set number value."""
        try:
            await self.entity_description.set_value(self._trait, value)
        except RoborockException as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="update_options_failed",
            ) from err


class RoborockNumberEntityQ10(RoborockCoordinatedEntityB01Q10, NumberEntity):
    """A class to set a numeric setting on a Roborock Q10 device."""

    entity_description: RoborockNumberDescriptionQ10
    coordinator: RoborockB01Q10UpdateCoordinator

    def __init__(
        self,
        unique_id: str,
        coordinator: RoborockB01Q10UpdateCoordinator,
        entity_description: RoborockNumberDescriptionQ10,
        trait: SoundVolumeTrait,
    ) -> None:
        """Create a number entity."""
        self.entity_description = entity_description
        self._trait = trait
        super().__init__(unique_id, coordinator)

    @override
    async def async_added_to_hass(self) -> None:
        """Register a trait listener for push-based state updates."""
        await super().async_added_to_hass()
        self.async_on_remove(self._trait.add_update_listener(self.async_write_ha_state))

    @property
    @override
    def native_value(self) -> float | None:
        """Get native value."""
        return self.entity_description.get_value(self._trait)

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set number value."""
        try:
            await self.entity_description.set_value(self._trait, value)
        except RoborockException as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="update_options_failed",
            ) from err


class RoborockNumberEntityA01(RoborockCoordinatedEntityA01, NumberEntity):
    """A class to set a numeric value on a Roborock A01 device."""

    entity_description: RoborockNumberDescriptionA01
    coordinator: RoborockWashingMachineUpdateCoordinator

    def __init__(
        self,
        coordinator: RoborockWashingMachineUpdateCoordinator,
        entity_description: RoborockNumberDescriptionA01,
    ) -> None:
        """Create an A01 number entity."""
        self.entity_description = entity_description
        super().__init__(
            f"{entity_description.key}_{coordinator.duid_slug}",
            coordinator,
        )

    @property
    @override
    def native_value(self) -> float | None:
        """Get the current value from coordinator data."""
        value = self.coordinator.data.get(self.entity_description.data_protocol)
        if value is None:
            return None
        return float(value)

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set number value."""
        try:
            await self.coordinator.api.set_value(
                self.entity_description.data_protocol,
                int(value),
            )
        except RoborockException as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="update_options_failed",
            ) from err
        await self.coordinator.async_request_refresh()
