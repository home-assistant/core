"""The Flexit Nordic (BACnet) integration."""

import asyncio.exceptions
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from flexit_bacnet import FlexitBACnet
from flexit_bacnet.bacnet import DecodingError

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue

from .const import DOMAIN
from .coordinator import FlexitConfigEntry, FlexitCoordinator
from .entity import FlexitEntity


@dataclass(kw_only=True, frozen=True)
class FlexitSwitchEntityDescription(SwitchEntityDescription):
    """Describes a Flexit switch entity."""

    is_on_fn: Callable[[FlexitBACnet], bool]
    turn_on_fn: Callable[[FlexitBACnet], Awaitable[None]]
    turn_off_fn: Callable[[FlexitBACnet], Awaitable[None]]


SWITCHES: tuple[FlexitSwitchEntityDescription, ...] = (
    FlexitSwitchEntityDescription(
        key="electric_heater",
        translation_key="electric_heater",
        is_on_fn=lambda data: data.electric_heater,
        turn_on_fn=lambda data: data.enable_electric_heater(),
        turn_off_fn=lambda data: data.disable_electric_heater(),
    ),
    FlexitSwitchEntityDescription(
        key="cooker_hood_mode",
        translation_key="cooker_hood_mode",
        is_on_fn=lambda data: data.cooker_hood_status,
        turn_on_fn=lambda data: data.activate_cooker_hood(),
        turn_off_fn=lambda data: data.deactivate_cooker_hood(),
    ),
    FlexitSwitchEntityDescription(
        key="fireplace_mode",
        translation_key="fireplace_mode",
        is_on_fn=lambda data: data.fireplace_ventilation_status,
        turn_on_fn=lambda data: data.trigger_fireplace_mode(),
        turn_off_fn=lambda data: data.trigger_fireplace_mode(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: FlexitConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Flexit (bacnet) switch from a config entry."""
    coordinator = config_entry.runtime_data

    entities: list[FlexitSwitch] = []
    for description in SWITCHES:
        if description.key == "fireplace_mode":
            # Check if deprecated fireplace switch is enabled and create repair issue
            entity_reg = er.async_get(hass)
            fireplace_switch_unique_id = (
                f"{coordinator.device.serial_number}-fireplace_mode"
            )
            # Look up the fireplace switch entity by unique_id
            fireplace_switch_entity_id = entity_reg.async_get_entity_id(
                Platform.SWITCH, DOMAIN, fireplace_switch_unique_id
            )
            if not fireplace_switch_entity_id:
                continue
            entity_registry_entry = entity_reg.async_get(fireplace_switch_entity_id)

            if entity_registry_entry:
                if entity_registry_entry.disabled:
                    entity_reg.async_remove(fireplace_switch_entity_id)
                else:
                    async_create_issue(
                        hass,
                        DOMAIN,
                        f"deprecated_switch_{fireplace_switch_unique_id}",
                        is_fixable=False,
                        issue_domain=DOMAIN,
                        severity=IssueSeverity.WARNING,
                        translation_key="deprecated_fireplace_switch",
                        translation_placeholders={
                            "entity_id": fireplace_switch_entity_id,
                        },
                    )
                    entities.append(FlexitSwitch(coordinator, description))
        else:
            entities.append(FlexitSwitch(coordinator, description))
        async_add_entities(entities)


PARALLEL_UPDATES = 1


class FlexitSwitch(FlexitEntity, SwitchEntity):
    """Representation of a Flexit Switch."""

    _attr_device_class = SwitchDeviceClass.SWITCH

    entity_description: FlexitSwitchEntityDescription

    def __init__(
        self,
        coordinator: FlexitCoordinator,
        entity_description: FlexitSwitchEntityDescription,
    ) -> None:
        """Initialize Flexit (bacnet) switch."""
        super().__init__(coordinator)

        self.entity_description = entity_description
        self._attr_unique_id = (
            f"{coordinator.device.serial_number}-{entity_description.key}"
        )

    @property
    def is_on(self) -> bool:
        """Return value of the switch."""
        return self.entity_description.is_on_fn(self.coordinator.data)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn switch on."""
        try:
            await self.entity_description.turn_on_fn(self.coordinator.data)
        except (asyncio.exceptions.TimeoutError, ConnectionError, DecodingError) as exc:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="switch_turn",
                translation_placeholders={
                    "state": "on",
                },
            ) from exc
        finally:
            await self.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn switch off."""
        try:
            await self.entity_description.turn_off_fn(self.coordinator.data)
        except (asyncio.exceptions.TimeoutError, ConnectionError, DecodingError) as exc:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="switch_turn",
                translation_placeholders={
                    "state": "off",
                },
            ) from exc
        finally:
            await self.coordinator.async_refresh()
