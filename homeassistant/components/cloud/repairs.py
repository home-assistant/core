"""Repairs implementation for the cloud integration."""
from __future__ import annotations

import asyncio
from typing import Any

from hass_nabucasa import Cloud
import voluptuous as vol

from homeassistant.components.repairs import RepairsFlow, repairs_flow_manager
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import issue_registry as ir

from .client import CloudClient
from .const import DOMAIN
from .subscription import async_migrate_paypal_agreement, async_subscription_info

BACKOFF_TIME = 5
MAX_RETRIES = 60  # This allows for 10 minutes of retries


@callback
def async_manage_legacy_subscription_issue(
    hass: HomeAssistant,
    subscription_info: dict[str, Any],
) -> None:
    """Manage the legacy subscription issue.

    If the provider is "legacy" create an issue,
    in all other cases remove the issue.
    """
    if subscription_info.get("provider") == "legacy":
        ir.async_create_issue(
            hass=hass,
            domain=DOMAIN,
            issue_id="legacy_subscription",
            is_fixable=True,
            severity=ir.IssueSeverity.WARNING,
            translation_key="legacy_subscription",
        )
        return
    ir.async_delete_issue(hass=hass, domain=DOMAIN, issue_id="legacy_subscription")


class LegacySubscriptionRepairFlow(RepairsFlow):
    """Handler for an issue fixing flow."""

    wait_task: asyncio.Task | None = None
    _data: dict[str, Any] | None = None

    async def async_step_init(self, _: None = None) -> FlowResult:
        """Handle the first step of a fix flow."""
        return await self.async_step_confirm_change_plan()

    async def async_step_confirm_change_plan(
        self,
        user_input: dict[str, str] | None = None,
    ) -> FlowResult:
        """Handle the confirm step of a fix flow."""
        if user_input is not None:
            return await self.async_step_change_plan()

        return self.async_show_form(
            step_id="confirm_change_plan", data_schema=vol.Schema({})
        )

    async def async_step_change_plan(self, _: None = None) -> FlowResult:
        """Wait for the user to authorize the app installation."""

        cloud: Cloud[CloudClient] = self.hass.data[DOMAIN]

        async def _async_wait_for_plan_change() -> None:
            flow_manager = repairs_flow_manager(self.hass)
            # We cannot get here without a flow manager
            assert flow_manager is not None

            retries = 0
            while retries < MAX_RETRIES:
                self._data = await async_subscription_info(cloud)
                if self._data is not None and self._data["provider"] != "legacy":
                    break

                retries += 1
                await asyncio.sleep(BACKOFF_TIME)

            self.hass.async_create_task(
                flow_manager.async_configure(flow_id=self.flow_id)
            )

        if not self.wait_task:
            self.wait_task = self.hass.async_create_task(_async_wait_for_plan_change())
            migration = await async_migrate_paypal_agreement(cloud)
            return self.async_external_step(
                step_id="change_plan",
                url=migration["url"] if migration else "https://account.nabucasa.com/",
            )

        await self.wait_task

        if self._data is None or self._data["provider"] == "legacy":
            # If we get here we waited too long.
            return self.async_external_step_done(next_step_id="timeout")

        return self.async_external_step_done(next_step_id="complete")

    async def async_step_complete(self, _: None = None) -> FlowResult:
        """Handle the final step of a fix flow."""
        return self.async_create_entry(data={})

    async def async_step_timeout(self, _: None = None) -> FlowResult:
        """Handle the final step of a fix flow."""
        return self.async_abort(reason="operation_took_too_long")


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create flow."""
    return LegacySubscriptionRepairFlow()
