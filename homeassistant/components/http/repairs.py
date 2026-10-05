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
    """Stage the stable config with an upgraded SSL profile and restart.

    The upgrade goes through the regular pending config trial: if the new
    profile locks the user out, it auto-reverts to the stable config.
    """

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Let the user pick the upgrade when there is more than one."""
        store = await async_get_and_load_store(self.hass)
        if store.pending is not None and store.pending[HTTP_CONFIG_ERROR] is None:
            # A pending config is under trial or waiting for its restart; the
            # upgrade must not replace it.
            return self.async_abort(reason="pending_config")
        upgrades = SSL_PROFILE_UPGRADES[SSLProfile(store.stable[CONF_SSL_PROFILE])]
        if len(upgrades) == 1:
            return await self._async_step_confirm(upgrades[0])
        return self.async_show_menu(
            step_id="init",
            menu_options=[f"confirm_{upgrade}" for upgrade in upgrades],
        )

    async def async_step_confirm_modern_v6(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Confirm the upgrade to the modern v6 profile."""
        return await self._async_step_confirm(SSLProfile.MODERN_V6, user_input)

    async def async_step_confirm_intermediate_v6(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Confirm the upgrade to the intermediate v6 profile."""
        return await self._async_step_confirm(SSLProfile.INTERMEDIATE_V6, user_input)

    async def _async_step_confirm(
        self, upgrade: SSLProfile, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Describe the upgrade and stage it once confirmed."""
        if user_input is None:
            return self.async_show_form(
                step_id=f"confirm_{upgrade}", data_schema=probatio.Schema({})
            )
        store = await async_get_and_load_store(self.hass)
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
