"""Test the Geocaching coordinator."""

from unittest.mock import MagicMock, patch

from geocachingapi.models import GeocachingSettings

from homeassistant.components.geocaching.const import (
    CONF_CACHE_CODES,
    CONF_TRACKABLE_CODES,
)
from homeassistant.components.geocaching.coordinator import (
    GeocachingDataUpdateCoordinator,
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

    with patch(
        "homeassistant.components.geocaching.coordinator.GeocachingApi"
    ) as geocaching_api_mock:
        GeocachingDataUpdateCoordinator(
            hass,
            entry=mock_config_entry,
            session=session,
        )

    geocaching_api_mock.assert_called_once()

    settings = geocaching_api_mock.call_args.kwargs["settings"]

    assert isinstance(settings, GeocachingSettings)
    assert settings.tracked_cache_codes == {"GC12345", "GC67890"}
    assert settings.tracked_trackable_codes == {"TB12345", "TB67890"}
