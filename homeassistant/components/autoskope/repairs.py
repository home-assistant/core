"""Repairs module for Autoskope integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.repairs import RepairsFlow
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import issue_registry as ir

from .const import DEFAULT_HOST, DOMAIN
from .models import AutoskopeApi, CannotConnect, InvalidAuth

_LOGGER = logging.getLogger(__name__)


def create_connection_issue(hass: HomeAssistant, entry_id: str) -> None:
    """Create an issue for connection errors."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        f"cannot_connect_{entry_id}",
        is_fixable=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key="cannot_connect",
        translation_placeholders={"entry_id": entry_id},
        data={"entry_id": entry_id},
    )


def create_auth_issue(hass: HomeAssistant, entry_id: str) -> None:
    """Create an issue for authentication errors."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        f"invalid_auth_{entry_id}",
        is_fixable=True,
        severity=ir.IssueSeverity.ERROR,
        translation_key="invalid_auth",
        translation_placeholders={"entry_id": entry_id},
        data={"entry_id": entry_id},
    )


class CannotConnectRepairFlow(RepairsFlow):
    """Handler for cannot connect repair flow."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the confirm step: try to authenticate again."""
        errors: dict[str, str] = {}
        entry_id: str | None = None
        description_placeholders: dict[str, str] = {}

        # Check if self.data is not None before accessing
        if self.data is not None:
            # Get entry_id, ensure it's treated as str or None
            entry_id_val = self.data.get("entry_id")
            if isinstance(entry_id_val, str):
                entry_id = entry_id_val
                description_placeholders["entry_id"] = entry_id
            elif entry_id_val is not None:
                _LOGGER.warning(
                    "Unexpected type for entry_id in repair data: %s",
                    type(entry_id_val),
                )

        if user_input is not None:
            if not entry_id:
                _LOGGER.error(
                    "Missing or invalid entry_id in repair flow data: %s", self.data
                )
                return self.async_abort(reason="unknown_error")

            entry = self.hass.config_entries.async_get_entry(entry_id)
            if not entry:
                _LOGGER.error("Config entry %s not found for repair", entry_id)
                return self.async_abort(reason="unknown_error")

            api = AutoskopeApi(
                host=entry.data.get(CONF_HOST, DEFAULT_HOST),
                username=entry.data[CONF_USERNAME],
                password=entry.data[CONF_PASSWORD],
                hass=self.hass,
            )
            try:
                await api.authenticate()
            except InvalidAuth:
                _LOGGER.warning(
                    "Authentication failed unexpectedly during connection repair for %s",
                    entry_id,
                )
                errors["base"] = "invalid_auth"
            except CannotConnect:
                _LOGGER.debug(
                    "Connection check failed again for entry %s during repair", entry_id
                )
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception(
                    "Unexpected error during connection check for repair for entry %s",
                    entry_id,
                )
                errors["base"] = "unknown"
            else:
                _LOGGER.debug(
                    "Connection check succeeded for entry %s during repair",
                    entry_id,
                )
                ir.async_delete_issue(self.hass, DOMAIN, self.issue_id)
                # Abort flow after successful repair
                return self.async_abort(reason="repaired")

        # Show confirmation form
        return self.async_show_form(
            step_id="confirm",
            errors=errors,
            description_placeholders=description_placeholders,
        )


class AuthFailureRepairsFlow(RepairsFlow):
    """Handler for the authentication failure repair flow."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the first step: show confirmation."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle confirmation step: trigger the standard reauth flow."""
        entry_id: str | None = None
        description_placeholders: dict[str, str] = {}

        # Check if self.data is not None before accessing
        if self.data is not None:
            # Get entry_id, ensure it's treated as str or None
            entry_id_val = self.data.get("entry_id")
            if isinstance(entry_id_val, str):
                entry_id = entry_id_val
                description_placeholders["entry_id"] = entry_id
            elif entry_id_val is not None:
                # Log if it's not a string but not None
                _LOGGER.warning(
                    "Unexpected type for entry_id in repair data: %s",
                    type(entry_id_val),
                )

        if user_input is None:
            # Show confirmation form
            return self.async_show_form(
                step_id="confirm", description_placeholders=description_placeholders
            )

        # User confirmed, trigger reauth
        # Check if entry_id is a valid string
        if not entry_id:
            _LOGGER.error(
                "Missing or invalid entry_id in auth repair flow data: %s", self.data
            )
            return self.async_abort(reason="unknown_error")

        _LOGGER.debug("Triggering reauth flow for entry %s from repair", entry_id)
        await self.hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "reauth", "entry_id": entry_id},
            data=None,
        )
        # Abort flow after triggering reauth
        return self.async_abort(reason="reauth_triggered")


async def async_create_fix_flow(
    hass: HomeAssistant, issue_id: str, data: dict[str, str | int | float | None] | None
) -> RepairsFlow:
    """Create flow to fix Autoskope issues."""
    flow: RepairsFlow | None = None

    if issue_id.startswith("cannot_connect"):
        flow = CannotConnectRepairFlow()
    elif issue_id.startswith("invalid_auth"):
        flow = AuthFailureRepairsFlow()
    else:
        raise ValueError(f"Unknown or unsupported repair issue ID: {issue_id}")

    flow.hass = hass
    flow.data = data
    flow.issue_id = issue_id
    return flow
