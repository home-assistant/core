"""Tests for Diagnostics."""

from homeassistant.components.aws_s3.diagnostics import (
    async_get_config_entry_diagnostics,
)
from homeassistant.core import HomeAssistant

from .const import CONF_SECRET_ACCESS_KEY, USER_INPUT_VALID_EXPLICIT

from tests.common import MockConfigEntry


async def test_diagnostics(hass: HomeAssistant) -> None:
    """Test the diagnostics method redaction."""
    result = await async_get_config_entry_diagnostics(
        hass, MockConfigEntry(data=USER_INPUT_VALID_EXPLICIT)
    )
    assert result["entry_data"] == USER_INPUT_VALID_EXPLICIT | {
        CONF_SECRET_ACCESS_KEY: "**REDACTED**"
    }
