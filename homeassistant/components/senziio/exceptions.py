"""Errors for Senziio integration."""

from homeassistant.exceptions import HomeAssistantError


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect to the device."""


class RepeatedTitle(HomeAssistantError):
    """Error to indicate that chosen device name is not unique."""


class MQTTNotEnabled(HomeAssistantError):
    """Error to indicate that required MQTT integration is not enabled."""
