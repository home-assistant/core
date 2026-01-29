"""YoLink select platform."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from yolink.client_request import ClientRequest
from yolink.const import ATTR_DEVICE_SPRINKLER
from yolink.device import YoLinkDevice
from yolink.message_resolver import sprinkler_message_resolve

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import YoLinkCoordinator
from .entity import YoLinkEntity


@dataclass(frozen=True, kw_only=True)
class YoLinkSelectEntityDescription(SelectEntityDescription):
    """YoLink SelectEntityDescription."""

    state_key: str = "state"
    exists_fn: Callable[[YoLinkDevice], bool] = lambda _: True
    should_update_entity: Callable = lambda state: True
    value: Callable = lambda data: data
    on_option_selected: Callable[[YoLinkCoordinator, str], Awaitable[bool]]


async def set_sprinker_mode_fn(coordinator: YoLinkCoordinator, option: str) -> bool:
    """Set sprinkler mode."""
    data: dict[str, Any] = await coordinator.call_device(
        ClientRequest(
            "setState",
            {
                "state": {
                    "mode": option,
                }
            },
        )
    )
    sprinkler_message_resolve(coordinator.device, data, None)
    coordinator.async_set_updated_data(data)
    return True


SELECTOR_MAPPINGS: tuple[YoLinkSelectEntityDescription, ...] = (
    YoLinkSelectEntityDescription(
        key="model",
        options=["auto", "manual", "off"],
        translation_key="sprinkler_mode",
        value=lambda data: (
            data.get("mode") if data is not None else None
        ),  # watering state report will missing state field
        exists_fn=lambda device: device.device_type == ATTR_DEVICE_SPRINKLER,
        should_update_entity=lambda value: value is not None,
        on_option_selected=set_sprinker_mode_fn,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up YoLink select from a config entry."""
    device_coordinators = hass.data[DOMAIN][config_entry.entry_id].device_coordinators
    async_add_entities(
        YoLinkSelectEntity(config_entry, selector_device_coordinator, description)
        for selector_device_coordinator in device_coordinators.values()
        if selector_device_coordinator.device.device_type in [ATTR_DEVICE_SPRINKLER]
        for description in SELECTOR_MAPPINGS
        if description.exists_fn(selector_device_coordinator.device)
    )


class YoLinkSelectEntity(YoLinkEntity, SelectEntity):
    """YoLink Select Entity."""

    entity_description: YoLinkSelectEntityDescription

    def __init__(
        self,
        config_entry: ConfigEntry,
        coordinator: YoLinkCoordinator,
        description: YoLinkSelectEntityDescription,
    ) -> None:
        """Init YoLink Select."""
        super().__init__(config_entry, coordinator)
        self.entity_description = description
        self._attr_unique_id = (
            f"{coordinator.device.device_id} {self.entity_description.key}"
        )

    @callback
    def update_entity_state(self, state: dict[str, Any]) -> None:
        """Update HA Entity State."""
        if (
            current_value := self.entity_description.value(
                state.get(self.entity_description.state_key)
            )
        ) is None and self.entity_description.should_update_entity(
            current_value
        ) is False:
            return
        self._attr_current_option = current_value
        self.async_write_ha_state()

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        if await self.entity_description.on_option_selected(self.coordinator, option):
            self._attr_current_option = option
            self.async_write_ha_state()
