"""Helpers for data entry flows for config entries."""
from typing import Any, Awaitable, Callable, Dict, Optional, Union

from homeassistant import config_entries

from .typing import HomeAssistantType

# mypy: allow-untyped-defs, no-check-untyped-defs

DiscoveryFunctionType = Callable[[], Union[Awaitable[bool], bool]]


class DiscoveryFlowHandler(config_entries.ConfigFlow):
    """Handle a discovery config flow."""

    VERSION = 1

    def __init__(
        self,
        domain: str,
        title: str,
        discovery_function: DiscoveryFunctionType,
        connection_class: str,
    ) -> None:
        """Initialize the discovery config flow."""
        self._domain = domain
        self._title = title
        self._discovery_function = discovery_function
        self.CONNECTION_CLASS = connection_class  # pylint: disable=invalid-name

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Handle a flow initialized by the user."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        await self.async_set_unique_id(self._domain, raise_on_progress=False)

        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Confirm setup."""
        if user_input is None:
            return self.async_show_form(step_id="confirm")

        if self.source == config_entries.SOURCE_USER:
            # Get current discovered entries.
            in_progress = self._async_in_progress()

            has_devices = in_progress
            if not has_devices:
                has_devices = await self.hass.async_add_job(  # type: ignore
                    self._discovery_function, self.hass
                )

            if not has_devices:
                return self.async_abort(reason="no_devices_found")

            # Cancel the discovered one.
            assert self.hass is not None
            for flow in in_progress:
                self.hass.config_entries.flow.async_abort(flow["flow_id"])

        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        return self.async_create_entry(title=self._title, data={})

    async def async_step_discovery(
        self, discovery_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle a flow initialized by discovery."""
        if self._async_in_progress() or self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        await self.async_set_unique_id(self._domain)

        return await self.async_step_confirm()

    async_step_zeroconf = async_step_discovery
    async_step_ssdp = async_step_discovery
    async_step_homekit = async_step_discovery

    async def async_step_import(self, _: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Handle a flow initialized by import."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        # Cancel other flows.
        assert self.hass is not None
        in_progress = self._async_in_progress()
        for flow in in_progress:
            self.hass.config_entries.flow.async_abort(flow["flow_id"])

        return self.async_create_entry(title=self._title, data={})


def register_discovery_flow(
    domain: str,
    title: str,
    discovery_function: DiscoveryFunctionType,
    connection_class: str,
) -> None:
    """Register flow for discovered integrations that not require auth."""

    class DiscoveryFlow(DiscoveryFlowHandler):
        """Discovery flow handler."""

        def __init__(self) -> None:
            super().__init__(domain, title, discovery_function, connection_class)

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
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Handle a user initiated set up flow to create a webhook."""
        if not self._allow_multiple and self._async_current_entries():
            return self.async_abort(reason="one_instance_allowed")

        if user_input is None:
            return self.async_show_form(step_id="user")

        assert self.hass is not None
        webhook_id = self.hass.components.webhook.async_generate_id()

        if (
            "cloud" in self.hass.config.components
            and self.hass.components.cloud.async_active_subscription()
        ):
            webhook_url = await self.hass.components.cloud.async_create_cloudhook(
                webhook_id
            )
            cloudhook = True
        else:
            webhook_url = self.hass.components.webhook.async_generate_url(webhook_id)
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
    hass: HomeAssistantType, entry: config_entries.ConfigEntry
) -> None:
    """Remove a webhook config entry."""
    if not entry.data.get("cloudhook") or "cloud" not in hass.config.components:
        return

    await hass.components.cloud.async_delete_cloudhook(entry.data["webhook_id"])
