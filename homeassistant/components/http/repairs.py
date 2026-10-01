"""Repairs for the HTTP integration."""

from typing import cast

import probatio

from homeassistant.components.homeassistant import (
    DOMAIN as HASS_DOMAIN,
    SERVICE_HOMEASSISTANT_RESTART,
)
from homeassistant.components.repairs import (
    ConfirmRepairFlow,
    RepairsFlow,
    RepairsFlowResult,
)
from homeassistant.core import HomeAssistant
from homeassistant.util.ssl import SSLProfile

from .config import HTTP_CONFIG_ERROR, ConfData, _strip_meta, async_get_and_load_store
from .const import CONF_SSL_PROFILE, ISSUE_SSL_PROFILE_OUTDATED, SSL_PROFILE_UPGRADES


class SSLProfileOutdatedFlow(RepairsFlow):
    """Stage the stable config with the upgraded SSL profile and restart.

    The upgrade goes through the regular pending config trial: if the new
    profile locks the user out, it auto-reverts to the stable config.
    """

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Handle the first step of a fix flow."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Handle the confirm step of a fix flow."""
        store = await async_get_and_load_store(self.hass)
        if store.pending is not None and store.pending[HTTP_CONFIG_ERROR] is None:
            # A pending config is under trial or waiting for its restart; the
            # upgrade must not replace it.
            return self.async_abort(reason="pending_config")
        profile = store.stable[CONF_SSL_PROFILE]
        upgrade = SSL_PROFILE_UPGRADES[SSLProfile(profile)]
        if user_input is None:
            return self.async_show_form(
                step_id="confirm",
                data_schema=probatio.Schema({}),
                description_placeholders={"profile": profile, "upgrade": upgrade},
            )
        await store.async_set_pending(
            cast(ConfData, {**_strip_meta(store.stable), CONF_SSL_PROFILE: upgrade})
        )
        await self.hass.services.async_call(HASS_DOMAIN, SERVICE_HOMEASSISTANT_RESTART)
        return self.async_create_entry(data={})


async def async_create_fix_flow(
    hass: HomeAssistant, issue_id: str, data: dict[str, str] | None
) -> RepairsFlow:
    """Create flow."""
    if issue_id == ISSUE_SSL_PROFILE_OUTDATED:
        return SSLProfileOutdatedFlow()
    return ConfirmRepairFlow()
