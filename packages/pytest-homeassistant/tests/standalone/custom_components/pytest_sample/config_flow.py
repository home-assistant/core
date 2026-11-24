"""Configuration flow for the standalone test integration."""

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult


class SampleConfigFlow(ConfigFlow, domain="pytest_sample"):
    """Create a sample config entry."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Set up the sample integration."""
        return self.async_create_entry(title="Sample", data={"state": "ready"})
