"""Test the Geocaching coordinator."""

from unittest.mock import AsyncMock, MagicMock, patch

from geocachingapi.models import GeocachingSettings, GeocachingStatus
import pytest

from homeassistant.components.geocaching.const import (
    DOMAIN,
    SUBENTRY_TYPE_TRACKABLE,
    SUBENTRY_TYPE_TRACKED_CACHE,
)
from homeassistant.config_entries import ConfigSubentryDataWithId
from homeassistant.const import CONF_CODE
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("subentries", "expected_cache_codes", "expected_trackable_codes"),
    [
        pytest.param(
            [
                ConfigSubentryDataWithId(
                    data={CONF_CODE: code},
                    subentry_type=SUBENTRY_TYPE_TRACKED_CACHE,
                    title=code,
                    unique_id=code,
                    subentry_id=f"cache-{code}",
                )
                for code in ("GC12345", "GC67890")
            ]
            + [
                ConfigSubentryDataWithId(
                    data={CONF_CODE: code},
                    subentry_type=SUBENTRY_TYPE_TRACKABLE,
                    title=code,
                    unique_id=code,
                    subentry_id=f"trackable-{code}",
                )
                for code in ("TB12345", "TB67890")
            ],
            {"GC12345", "GC67890"},
            {"TB12345", "TB67890"},
            id="configured",
        ),
        pytest.param([], set(), set(), id="no-subentries"),
    ],
)
async def test_coordinator_uses_tracked_cache_and_trackable_codes(
    hass: HomeAssistant,
    subentries: list[ConfigSubentryDataWithId],
    expected_cache_codes: set[str],
    expected_trackable_codes: set[str],
) -> None:
    """Test that tracked codes are passed to Geocaching settings."""
    config_entry = MockConfigEntry(
        title="1234AB 1",
        domain=DOMAIN,
        data={"id": "mock_user", "auth_implementation": DOMAIN},
        unique_id="mock_user",
        subentries_data=subentries,
    )
    config_entry.add_to_hass(hass)

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
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    geocaching_api_mock.assert_called_once()

    settings = geocaching_api_mock.call_args.kwargs["settings"]

    assert isinstance(settings, GeocachingSettings)
    assert settings.tracked_cache_codes == expected_cache_codes
    assert settings.tracked_trackable_codes == expected_trackable_codes
