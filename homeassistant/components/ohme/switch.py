"""Platform for switch."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from ohme import ApiException, OhmeApiClient

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import OhmeConfigEntry
from .entity import OhmeEntity, OhmeEntityDescription

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class OhmeConfigSwitchDescription(OhmeEntityDescription, SwitchEntityDescription):
    """Class describing Ohme configuration switch entities."""

    configuration_key: str


@dataclass(frozen=True, kw_only=True)
class OhmeSwitchDescription(OhmeEntityDescription, SwitchEntityDescription):
    """Class describing basic Ohme switch entities."""

    is_on_fn: Callable[[OhmeApiClient], bool]
    off_fn: Callable[[OhmeApiClient], Awaitable]
    on_fn: Callable[[OhmeApiClient], Awaitable]


SWITCH_CONFIG = [
    OhmeConfigSwitchDescription(
        key="lock_buttons",
        translation_key="lock_buttons",
        entity_category=EntityCategory.CONFIG,
        is_supported_fn=lambda client: client.is_capable("buttonsLockable"),
        configuration_key="buttonsLocked",
    ),
    OhmeConfigSwitchDescription(
        key="require_approval",
        translation_key="require_approval",
        entity_category=EntityCategory.CONFIG,
        is_supported_fn=lambda client: client.is_capable("pluginsRequireApprovalMode"),
        configuration_key="pluginsRequireApproval",
    ),
    OhmeConfigSwitchDescription(
        key="sleep_when_inactive",
        translation_key="sleep_when_inactive",
        entity_category=EntityCategory.CONFIG,
        is_supported_fn=lambda client: client.is_capable("stealth"),
        configuration_key="stealthEnabled",
    ),
]

SWITCH_DESCRIPTION = [
    OhmeSwitchDescription(
        key="price_cap",
        translation_key="price_cap",
        is_supported_fn=lambda client: client.cap_available,
        is_on_fn=lambda client: client.cap_enabled,
        on_fn=lambda client: client.async_change_price_cap(True),
        off_fn=lambda client: client.async_change_price_cap(False),
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: OhmeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up switches."""
    coordinator = config_entry.runtime_data.device_info_coordinator

    async_add_entities(
        OhmeConfigSwitch(coordinator, description)
        for description in SWITCH_CONFIG
        if description.is_supported_fn(coordinator.client)
    )

    async_add_entities(
        OhmeSwitch(coordinator, description)
        for description in SWITCH_DESCRIPTION
        if description.is_supported_fn(coordinator.client)
    )


class OhmeSwitch(OhmeEntity, SwitchEntity):
    """Generic switch for Ohme."""

    entity_description: OhmeSwitchDescription

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        return self.entity_description.is_on_fn(self.coordinator.client)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.entity_description.off_fn(self.coordinator.client)
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.entity_description.on_fn(self.coordinator.client)
        await self.coordinator.async_request_refresh()


class OhmeConfigSwitch(OhmeEntity, SwitchEntity):
    """Configuration switch for Ohme."""

    entity_description: OhmeConfigSwitchDescription

    @property
    def is_on(self) -> bool:
        """Return the entity value to represent the entity state."""
        return self.coordinator.client.configuration_value(
            self.entity_description.configuration_key
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._toggle(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._toggle(False)

    async def _toggle(self, on: bool) -> None:
        """Toggle the switch."""
        try:
            await self.coordinator.client.async_set_configuration_value(
                {self.entity_description.configuration_key: on}
            )
        except ApiException as e:
            raise HomeAssistantError(
                translation_key="api_failed", translation_domain=DOMAIN
            ) from e
        await self.coordinator.async_request_refresh()
