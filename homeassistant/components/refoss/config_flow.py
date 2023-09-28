"""ConfigFlow for Refoss."""

from __future__ import annotations

from refoss_ha.exceptions import RefossSocketInitErr

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import discovery_flow
from homeassistant.helpers.typing import DiscoveryInfoType

from .const import DOMAIN
from .models import HomeAssistantRefossData
from .util import get_refoss_socket_server


class RefossConfigFlow(ConfigFlow, domain=DOMAIN):
    """RefossConfigFlow for Refoss."""

    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle a flow  by user."""
        try:
            socketserver = await get_refoss_socket_server(self.hass)
            socketserver.register_message_received(self.message_received)
            return self.async_abort(reason="discovering_device")
        except RefossSocketInitErr:
            return self.async_abort(reason="socket_start_fail")

    @callback
    def message_received(self, data: dict):
        """Receive socket messages."""
        if "channels" in data and "uuid" in data:
            discovery_flow.async_create_flow(
                self.hass,
                DOMAIN,
                context={"source": config_entries.SOURCE_DISCOVERY},
                data=data,
            )

        elif "header" in data and "payload" in data:
            self.hass.create_task(self.async_update_push_state(data=data))

    async def async_step_discovery(
        self, discovery_info: DiscoveryInfoType
    ) -> FlowResult:
        """Handle a flow initialized by discovery."""
        uuid = discovery_info["uuid"]
        host = discovery_info["ip"]
        device_name = discovery_info["devName"]

        if (
            current_entry := await self.async_set_unique_id(uuid)
        ) and current_entry.data.get("ip") == host:
            return self.async_abort(reason="already_configured")

        self._abort_if_unique_id_configured(updates=discovery_info)

        return self.async_create_entry(title=device_name, data=discovery_info)

    async def async_update_push_state(self, data: dict) -> None:
        """Async update the status of device."""
        header = data["header"]
        uuid = header["uuid"]
        if entry := await self.async_set_unique_id(uuid):
            namespace = header["namespace"]
            payload = data["payload"]
            refoss_data: HomeAssistantRefossData = self.hass.data[DOMAIN][
                entry.entry_id
            ]
            await refoss_data.base_device.async_handle_push_notification(
                namespace, payload, uuid
            )
