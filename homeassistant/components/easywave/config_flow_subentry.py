"""Subentry config flows for adding Easywave child devices."""

from typing import Any

from homeassistant.config_entries import ConfigSubentryFlow, SubentryFlowResult

from .config_flow_device import EasywaveDeviceAddFlowMixin


class EasywaveTransmitterSubentryFlowHandler(
    ConfigSubentryFlow, EasywaveDeviceAddFlowMixin
):
    """Handle adding Easywave transmitters to the RX11 hub."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize."""
        super().__init__(*args, **kwargs)
        self._init_device_flow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Entry point for adding an Easywave transmitter."""
        return await self.async_step_transmitter()


class EasywaveNeoSensorSubentryFlowHandler(
    ConfigSubentryFlow, EasywaveDeviceAddFlowMixin
):
    """Handle adding Easywave neo sensors to the RX11 hub."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize."""
        super().__init__(*args, **kwargs)
        self._init_device_flow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Entry point for adding an Easywave neo sensor."""
        return await self.async_step_neo_sensor()
