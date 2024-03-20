"""Helpers for data entry flows for config entries."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
import logging
from typing import TYPE_CHECKING, Any, Generic, TypeVar, cast

from homeassistant import config_entries
from homeassistant.components import onboarding
from homeassistant.core import HomeAssistant

from .typing import DiscoveryInfoType

if TYPE_CHECKING:
    import asyncio

    from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
    from homeassistant.components.dhcp import DhcpServiceInfo
    from homeassistant.components.ssdp import SsdpServiceInfo
    from homeassistant.components.zeroconf import ZeroconfServiceInfo

    from .service_info.mqtt import MqttServiceInfo

_R = TypeVar("_R", bound="Awaitable[bool] | bool")
DiscoveryFunctionType = Callable[[HomeAssistant], _R]

_LOGGER = logging.getLogger(__name__)


class DiscoveryFlowHandler(config_entries.ConfigFlow, Generic[_R]):
    """Handle a discovery config flow."""

    VERSION = 1

    def __init__(
        self,
        domain: str,
        title: str,
        discovery_function: DiscoveryFunctionType[_R],
    ) -> None:
        """Initialize the discovery config flow."""
        self._domain = domain
        self._title = title
        self._discovery_function = discovery_function

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow initialized by the user."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        await self.async_set_unique_id(self._domain, raise_on_progress=False)

        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Confirm setup."""
        if user_input is None and onboarding.async_is_onboarded(self.hass):
            self._set_confirm_only()
            return self.async_show_form(step_id="confirm")

        if self.source == config_entries.SOURCE_USER:
            # Get current discovered entries.
            in_progress = self._async_in_progress()

            if not (has_devices := bool(in_progress)):
                has_devices = await cast(
                    "asyncio.Future[bool]", self._discovery_function(self.hass)
                )

            if not has_devices:
                return self.async_abort(reason="no_devices_found")

            # Cancel the discovered one.
            for flow in in_progress:
                self.hass.config_entries.flow.async_abort(flow["flow_id"])

        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        return self.async_create_entry(title=self._title, data={})

    async def async_step_discovery(
        self, discovery_info: DiscoveryInfoType
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow initialized by discovery."""
        if self._async_in_progress() or self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        await self.async_set_unique_id(self._domain)

        return await self.async_step_confirm()

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow initialized by bluetooth discovery."""
        if self._async_in_progress() or self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        await self.async_set_unique_id(self._domain)

        return await self.async_step_confirm()

    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow initialized by dhcp discovery."""
        if self._async_in_progress() or self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        await self.async_set_unique_id(self._domain)

        return await self.async_step_confirm()

    async def async_step_homekit(
        self, discovery_info: ZeroconfServiceInfo
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow initialized by Homekit discovery."""
        if self._async_in_progress() or self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        await self.async_set_unique_id(self._domain)

        return await self.async_step_confirm()

    async def async_step_mqtt(
        self, discovery_info: MqttServiceInfo
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow initialized by mqtt discovery."""
        if self._async_in_progress() or self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        await self.async_set_unique_id(self._domain)

        return await self.async_step_confirm()

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow initialized by Zeroconf discovery."""
        if self._async_in_progress() or self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        await self.async_set_unique_id(self._domain)

        return await self.async_step_confirm()

    async def async_step_ssdp(
        self, discovery_info: SsdpServiceInfo
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow initialized by Ssdp discovery."""
        if self._async_in_progress() or self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        await self.async_set_unique_id(self._domain)

        return await self.async_step_confirm()

    async def async_step_import(
        self, _: dict[str, Any] | None
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow initialized by import."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        # Cancel other flows.
        in_progress = self._async_in_progress()
        for flow in in_progress:
            self.hass.config_entries.flow.async_abort(flow["flow_id"])

        return self.async_create_entry(title=self._title, data={})


def register_discovery_flow(
    domain: str,
    title: str,
    discovery_function: DiscoveryFunctionType[Awaitable[bool] | bool],
) -> None:
    """Register flow for discovered integrations that not require auth."""

    class DiscoveryFlow(DiscoveryFlowHandler[Awaitable[bool] | bool]):
        """Discovery flow handler."""

        def __init__(self) -> None:
            super().__init__(domain, title, discovery_function)

    config_entries.HANDLERS.register(domain)(DiscoveryFlow)


class WebhookFlowHandler(config_entries.ConfigFlow):
    """Handle a webhook config flow."""

    VERSION = 1

    def __init__(
        self,
        domain: str,
        title: str,
        description_placeholder: dict,
        allow_multiple: bool,
    ) -> None:
        """Initialize the discovery config flow."""
        self._domain = domain
        self._title = title
        self._description_placeholder = description_placeholder
        self._allow_multiple = allow_multiple

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle a user initiated set up flow to create a webhook."""
        if not self._allow_multiple and self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is None:
            return self.async_show_form(step_id="user")

        # Local import to be sure cloud is loaded and setup
        # pylint: disable-next=import-outside-toplevel
        from homeassistant.components.cloud import (
            async_active_subscription,
            async_create_cloudhook,
            async_is_connected,
        )

        # Local import to be sure webhook is loaded and setup
        # pylint: disable-next=import-outside-toplevel
        from homeassistant.components.webhook import (
            async_generate_id,
            async_generate_url,
        )

        webhook_id = async_generate_id()

        if "cloud" in self.hass.config.components and async_active_subscription(
            self.hass
        ):
            if not async_is_connected(self.hass):
                return self.async_abort(reason="cloud_not_connected")

            webhook_url = await async_create_cloudhook(self.hass, webhook_id)
            cloudhook = True
        else:
            webhook_url = async_generate_url(self.hass, webhook_id)
            cloudhook = False

        self._description_placeholder["webhook_url"] = webhook_url

        return self.async_create_entry(
            title=self._title,
            data={"webhook_id": webhook_id, "cloudhook": cloudhook},
            description_placeholders=self._description_placeholder,
        )


def register_webhook_flow(
    domain: str, title: str, description_placeholder: dict, allow_multiple: bool = False
) -> None:
    """Register flow for webhook integrations."""

    class WebhookFlow(WebhookFlowHandler):
        """Webhook flow handler."""

        def __init__(self) -> None:
            super().__init__(domain, title, description_placeholder, allow_multiple)

    config_entries.HANDLERS.register(domain)(WebhookFlow)


async def webhook_async_remove_entry(
    hass: HomeAssistant, entry: config_entries.ConfigEntry
) -> None:
    """Remove a webhook config entry."""
    if not entry.data.get("cloudhook") or "cloud" not in hass.config.components:
        return

    # Local import to be sure cloud is loaded and setup
    # pylint: disable-next=import-outside-toplevel
    from homeassistant.components.cloud import async_delete_cloudhook

    await async_delete_cloudhook(hass, entry.data["webhook_id"])
