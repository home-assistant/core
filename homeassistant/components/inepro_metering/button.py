"""Button platform for TCP gateway configuration actions."""

from inepro_metering.gateway_settings import (
    GatewayActionDescription,
    get_gateway_actions,
)

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .gateway_support import IneproGatewayEntity, entry_supports_gateway_management


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up TCP gateway buttons from a config entry."""
    del hass
    if not entry_supports_gateway_management(entry):
        return

    coordinator = entry.runtime_data
    async_add_entities(
        [
            IneproGatewayButton(coordinator, entry, action)
            for action in get_gateway_actions()
        ]
    )


class IneproGatewayButton(
    IneproGatewayEntity,
    ButtonEntity,
):
    """Expose one shared-library gateway action button."""

    def __init__(
        self,
        coordinator,
        entry: ConfigEntry,
        action: GatewayActionDescription,
    ) -> None:
        """Initialize the gateway action button."""
        super().__init__(coordinator, entry)
        self._action = action
        self._attr_name = action.name
        self._attr_unique_id = f"{entry.entry_id}_gateway_{action.key}_button"

    async def async_press(self) -> None:
        """Execute the configured gateway action."""
        await self.coordinator.async_execute_gateway_action(action_key=self._action.key)
        await self.coordinator.async_request_refresh()
