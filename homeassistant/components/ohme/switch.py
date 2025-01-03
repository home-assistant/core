"""Platform for switch."""

from dataclasses import dataclass
from typing import Any

from ohme import ApiException

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

    configuration_key: str


SWITCH_DEVICE_INFO = [
    OhmeSwitchDescription(
        key="lock_buttons",
        translation_key="lock_buttons",
        entity_category=EntityCategory.CONFIG,
        is_supported_fn=lambda client: client.is_capable("buttonsLockable"),
        configuration_key="buttonsLocked",
    ),
    OhmeSwitchDescription(
        key="require_approval",
        translation_key="require_approval",
        entity_category=EntityCategory.CONFIG,
        is_supported_fn=lambda client: client.is_capable("pluginsRequireApprovalMode"),
        configuration_key="pluginsRequireApproval",
    ),
    OhmeSwitchDescription(
        key="sleep_when_inactive",
        translation_key="sleep_when_inactive",
        entity_category=EntityCategory.CONFIG,
        is_supported_fn=lambda client: client.is_capable("stealth"),
        configuration_key="stealthEnabled",
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
