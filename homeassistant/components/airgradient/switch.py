"""Support for AirGradient switch entities."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, override

from airgradient import AirGradientClient, Config
from airgradient.models import ConfigurationControl

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AirGradientConfigEntry
from .const import DOMAIN, supports_config
from .coordinator import AirGradientCoordinator
from .entity import AirGradientEntity, exception_handler

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class AirGradientSwitchEntityDescription(SwitchEntityDescription):
    """Describes AirGradient switch entity."""

    config_key: str
    value_fn: Callable[[Config], bool | None]
    set_value_fn: Callable[[AirGradientClient, bool], Awaitable[None]]


POST_DATA_TO_AIRGRADIENT = AirGradientSwitchEntityDescription(
    key="post_data_to_airgradient",
    translation_key="post_data_to_airgradient",
    entity_category=EntityCategory.CONFIG,
    config_key="post_data_to_airgradient",
    value_fn=lambda config: config.post_data_to_airgradient,
    set_value_fn=lambda client, value: client.enable_sharing_data(enable=value),
)

BUZZER_ENABLED = AirGradientSwitchEntityDescription(
    key="buzzer_enabled",
    translation_key="buzzer_enabled",
    entity_category=EntityCategory.CONFIG,
    config_key="buzzer_enabled",
    value_fn=lambda config: config.buzzer_enabled,
    set_value_fn=lambda client, value: client.set_buzzer_enabled(value),
)

CLOUD_CONNECTION = AirGradientSwitchEntityDescription(
    key="cloud_connection",
    translation_key="cloud_connection",
    entity_category=EntityCategory.CONFIG,
    config_key="cloud_connection",
    value_fn=lambda config: config.cloud_connection,
    set_value_fn=lambda client, value: client.set_cloud_connection(value),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirGradientConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up AirGradient switch entities based on a config entry."""
    coordinator = entry.runtime_data
    descriptions = (POST_DATA_TO_AIRGRADIENT, BUZZER_ENABLED, CLOUD_CONNECTION)
    descriptions_by_key = {description.key: description for description in descriptions}
    added_entities: set[str] = set()

    @callback
    def _async_check_entities() -> None:
        nonlocal added_entities
        config = coordinator.data.config
        desired_entities = {
            description.key
            for description in descriptions
            if config.configuration_control is ConfigurationControl.LOCAL
            and supports_config(
                coordinator.data.measures.model,
                coordinator.client.api_version,
                config,
                description.config_key,
            )
        }

        if entities_to_add := desired_entities - added_entities:
            async_add_entities(
                [
                    AirGradientSwitch(coordinator, descriptions_by_key[key])
                    for key in entities_to_add
                ]
            )
        if entities_to_remove := added_entities - desired_entities:
            entity_registry = er.async_get(hass)
            for key in entities_to_remove:
                unique_id = f"{coordinator.serial_number}-{key}"
                if entity_id := entity_registry.async_get_entity_id(
                    SWITCH_DOMAIN, DOMAIN, unique_id
                ):
                    entity_registry.async_remove(entity_id)
        added_entities = desired_entities

    coordinator.async_add_listener(_async_check_entities)
    _async_check_entities()


class AirGradientSwitch(AirGradientEntity, SwitchEntity):
    """Defines an AirGradient switch entity."""

    entity_description: AirGradientSwitchEntityDescription

    def __init__(
        self,
        coordinator: AirGradientCoordinator,
        description: AirGradientSwitchEntityDescription,
    ) -> None:
        """Initialize AirGradient switch."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.serial_number}-{description.key}"

    @property
    @override
    def is_on(self) -> bool | None:
        """Return the state of the switch."""
        return self.entity_description.value_fn(self.coordinator.data.config)

    @exception_handler
    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.entity_description.set_value_fn(self.coordinator.client, True)
        await self.coordinator.async_request_refresh()

    @exception_handler
    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.entity_description.set_value_fn(self.coordinator.client, False)
        await self.coordinator.async_request_refresh()
