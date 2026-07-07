"""Subentry config flow for adding Easywave child devices."""

from typing import Any

from homeassistant.config_entries import ConfigSubentryFlow, SubentryFlowResult

from .config_flow_device import EasywaveDeviceAddFlowMixin
from .const import SUBENTRY_TYPE_NEO_SENSOR, SUBENTRY_TYPE_TRANSMITTER


class EasywaveDeviceSubentryFlowHandler(ConfigSubentryFlow, EasywaveDeviceAddFlowMixin):
    """Handle adding transmitters and neo sensors to the RX11 hub."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize."""
        super().__init__(*args, **kwargs)
        self._init_device_flow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Entry point for adding a transmitter or neo sensor."""
        return await self.async_step_device_select()

    async def async_step_device_select(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Let the user pick a transmitter or neo sensor."""
        return self.async_show_menu(
            step_id="device_select",
            menu_options=[SUBENTRY_TYPE_TRANSMITTER, SUBENTRY_TYPE_NEO_SENSOR],
        )
