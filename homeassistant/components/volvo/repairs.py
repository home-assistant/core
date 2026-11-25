"""Repairs for the Volvo integration."""

from typing import TYPE_CHECKING, Any

from volvocarsapi.auth import is_legacy_client

from homeassistant.components.repairs import FlowType, RepairsFlow, RepairsFlowResult
from homeassistant.config_entries import SOURCE_REAUTH
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
                # Aborting keeps the issue until the reload after a successful
                # reauth removes it
                return self.async_abort(
                    reason="reauth_started",
                    next_flow=(FlowType.CONFIG_FLOW, await self._async_reauth()),
                )

            errors["base"] = "no_new_credential"

        return self.async_show_form(
            step_id="confirm",
            errors=errors,
            description_placeholders={
                "name": self._entry.title,
                "volvo_dev_portal": VOLVO_DEV_PORTAL_URL,
            },
        )

    async def _async_reauth(self) -> str:
        """Return the ID of the reauth flow of the entry, starting one if needed."""
        for flow in self._entry.async_get_active_flows(self.hass, {SOURCE_REAUTH}):
            return flow["flow_id"]

        result = await self.hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": SOURCE_REAUTH,
                "entry_id": self._entry.entry_id,
                "title_placeholders": {"name": self._entry.title},
                "unique_id": self._entry.unique_id,
            },
            data=self._entry.data,
        )
        return result["flow_id"]

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
