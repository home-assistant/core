"""Repairs for the Volvo integration."""

from typing import TYPE_CHECKING, Any

from volvocarsapi.auth import is_legacy_client

from homeassistant.components.repairs import RepairsFlow, RepairsFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import (
    LocalOAuth2Implementation,
    async_get_implementations,
)

from .const import DOMAIN, VOLVO_DEV_PORTAL_URL
from .coordinator import VolvoConfigEntry


class VolvoIdMigrationRepairFlow(RepairsFlow):
    """Start reauth to migrate to the new Volvo ID system."""

    def __init__(self, entry: VolvoConfigEntry) -> None:
        """Initialize the repair flow."""
        self._entry = entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> RepairsFlowResult:
        """Handle the first step of the repair flow."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> RepairsFlowResult:
        """Confirm and start reauth."""
        errors: dict[str, str] = {}

        if user_input is not None:
            if await self._async_has_new_credential():
                self._entry.async_start_reauth(self.hass)
                return self.async_create_entry(data={})

            errors["base"] = "no_new_credential"

        return self.async_show_form(
            step_id="confirm",
            errors=errors,
            description_placeholders={
                "name": self._entry.title,
                "volvo_dev_portal": VOLVO_DEV_PORTAL_URL,
            },
        )

    async def _async_has_new_credential(self) -> bool:
        implementations = await async_get_implementations(self.hass, DOMAIN)
        return any(
            isinstance(implementation, LocalOAuth2Implementation)
            and not is_legacy_client(implementation.client_id)
            for implementation in implementations.values()
        )


async def async_create_fix_flow(
    hass: HomeAssistant, issue_id: str, data: dict[str, Any] | None
) -> RepairsFlow:
    """Create the repair flow for the Volvo ID migration."""
    if TYPE_CHECKING:
        assert data is not None
    return VolvoIdMigrationRepairFlow(
        hass.config_entries.async_get_known_entry(data["entry_id"])
    )
