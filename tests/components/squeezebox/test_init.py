"""Test squeezebox initialization."""

from unittest.mock import patch

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_init_api_fail(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test init fail due to API fail."""

    # Setup component to fail...
    with (
        patch(
            "homeassistant.components.squeezebox.Server.async_query",
            return_value=False,
        ),
    ):
        assert not await hass.config_entries.async_setup(config_entry.entry_id)
