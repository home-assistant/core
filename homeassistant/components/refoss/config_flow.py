"""ConfigFlow for Refoss."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigFlow
from homeassistant.data_entry_flow import FlowResult
from homeassistant.const import CONF_MAC

from refoss_ha.util import get_mac_address
from refoss_ha.const import DOMAIN


class RefossConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        # ha Host MAC address
        mac = get_mac_address()
        entry = await self.async_set_unique_id(mac)

        data = {
            CONF_MAC: mac,
        }
        if entry is not None:
            self._abort_if_unique_id_configured(updates=data, reload_on_update=True)
            await self.hass.config_entries.async_reload(entry.entry_id)
            return

        return self.async_create_entry(title="Refoss", data=data)
