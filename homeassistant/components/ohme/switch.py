"""Platform for switch."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from ohme import ApiException, ChargerStatus, OhmeApiClient

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import OhmeConfigEntry
from .const import DOMAIN
from .entity import OhmeEntity, OhmeEntityDescription

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class OhmeSwitchDescription(OhmeEntityDescription, SwitchEntityDescription):
    """Class describing Ohme switch entities."""

    is_on_fn: Callable[[OhmeApiClient], bool]
    turn_on_fn: Callable[[OhmeApiClient], Coroutine[Any, Any, Any]]
    turn_off_fn: Callable[[OhmeApiClient], Coroutine[Any, Any, Any]]


SWITCH_CHARGE_SESSION = [
    OhmeSwitchDescription(
        key="pause_charge",
        translation_key="pause_charge",
        is_on_fn=lambda client: client.status is ChargerStatus.PAUSED,
        turn_on_fn=lambda client: client.async_pause_charge(),
        turn_off_fn=lambda client: client.async_resume_charge(),
        available_fn=lambda client: client.status is not ChargerStatus.UNPLUGGED,
    ),
    OhmeSwitchDescription(
        key="max_charge",
        translation_key="max_charge",
        is_on_fn=lambda client: client.max_charge,
        turn_on_fn=lambda client: client.async_max_charge(state=True),
        turn_off_fn=lambda client: client.async_max_charge(state=False),
        available_fn=lambda client: client.status is not ChargerStatus.UNPLUGGED,
    ),
]

SWITCH_DEVICE_INFO = [
    OhmeSwitchDescription(
        key="lock_buttons",
        translation_key="lock_buttons",
        entity_category=EntityCategory.CONFIG,
        is_supported_fn=lambda client: client.is_capable("buttonsLockable"),
        is_on_fn=lambda client: client.configuration_value("buttonsLocked"),
        turn_on_fn=lambda client: client.async_set_configuration_value(
            {"buttonsLocked": True}
        ),
        turn_off_fn=lambda client: client.async_set_configuration_value(
            {"buttonsLocked": False}
        ),
    ),
    OhmeSwitchDescription(
        key="require_approval",
        translation_key="require_approval",
        entity_category=EntityCategory.CONFIG,
        is_supported_fn=lambda client: client.is_capable("pluginsRequireApprovalMode"),
        is_on_fn=lambda client: client.configuration_value("pluginsRequireApproval"),
        turn_on_fn=lambda client: client.async_set_configuration_value(
            {"pluginsRequireApproval": True}
        ),
        turn_off_fn=lambda client: client.async_set_configuration_value(
            {"pluginsRequireApproval": False}
        ),
    ),
    OhmeSwitchDescription(
        key="sleep_when_inactive",
        translation_key="sleep_when_inactive",
        entity_category=EntityCategory.CONFIG,
        is_supported_fn=lambda client: client.is_capable("stealth"),
        is_on_fn=lambda client: client.configuration_value("stealthEnabled"),
        turn_on_fn=lambda client: client.async_set_configuration_value(
            {"stealthEnabled": True}
        ),
        turn_off_fn=lambda client: client.async_set_configuration_value(
            {"stealthEnabled": False}
        ),
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: OhmeConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switches."""
    coordinators = config_entry.runtime_data
    coordinator_map = [
        (SWITCH_CHARGE_SESSION, coordinators.charge_session_coordinator),
        (SWITCH_DEVICE_INFO, coordinators.device_info_coordinator),
    ]

    async_add_entities(
        OhmeSwitch(coordinator, description)
        for entities, coordinator in coordinator_map
        for description in entities
        if description.is_supported_fn(coordinator.client)
    )


class OhmeSwitch(OhmeEntity, SwitchEntity):
    """Generic switch for Ohme."""

    entity_description: OhmeSwitchDescription

    @property
    def is_on(self) -> bool:
        """Return the entity value to represent the entity state."""
        return self.entity_description.is_on_fn(self.coordinator.client)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        try:
            await self.entity_description.turn_on_fn(self.coordinator.client)
        except ApiException as e:
            raise HomeAssistantError(
                translation_key="api_failed", translation_domain=DOMAIN
            ) from e
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        try:
            await self.entity_description.turn_off_fn(self.coordinator.client)
        except ApiException as e:
            raise HomeAssistantError(
                translation_key="api_failed", translation_domain=DOMAIN
            ) from e
        await self.coordinator.async_request_refresh()
