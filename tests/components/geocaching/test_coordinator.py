"""Test the Geocaching coordinator."""

from unittest.mock import AsyncMock, MagicMock, patch

from geocachingapi.models import GeocachingSettings, GeocachingStatus

from homeassistant.components.geocaching.const import (
    CONF_CACHE_CODES,
    CONF_TRACKABLE_CODES,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_coordinator_uses_tracked_cache_and_trackable_codes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that tracked cache codes are passed to Geocaching settings."""
    mock_config_entry.add_to_hass(hass)

    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={
            CONF_CACHE_CODES: ["GC12345", "GC67890"],
            CONF_TRACKABLE_CODES: ["TB12345", "TB67890"],
        },
    )

    session = MagicMock()
    session.token = {"access_token": "mock-token"}

    with (
        patch(
            "homeassistant.components.geocaching.async_get_config_entry_implementation",
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.components.geocaching.OAuth2Session",
            return_value=session,
        ),
        patch(
            "homeassistant.components.geocaching.coordinator.GeocachingApi"
        ) as geocaching_api_mock,
    ):
        geocaching_api_mock.return_value.update = AsyncMock(
            return_value=GeocachingStatus()
        )
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    geocaching_api_mock.assert_called_once()

    settings = geocaching_api_mock.call_args.kwargs["settings"]

    assert isinstance(settings, GeocachingSettings)
    assert settings.tracked_cache_codes == {"GC12345", "GC67890"}
    assert settings.tracked_trackable_codes == {"TB12345", "TB67890"}
