"""Test the Geocaching coordinator."""

from unittest.mock import AsyncMock, MagicMock, patch

from geocachingapi.models import (
    GeocachingCache,
    GeocachingSettings,
    GeocachingStatus,
    GeocachingTrackable,
)
import pytest

from homeassistant.components.geocaching.const import (
    CONF_TRACKABLE_CODES,
    DOMAIN,
    SUBENTRY_TYPE_TRACKED_CACHE,
)
from homeassistant.config_entries import ConfigSubentryDataWithId
from homeassistant.const import CONF_CODE
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("subentries", "options", "expected_cache_codes", "expected_trackable_codes"),
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
            ],
            {CONF_TRACKABLE_CODES: ["TB12345", "TB67890"]},
            {"GC12345", "GC67890"},
            {"TB12345", "TB67890"},
            id="configured",
        ),
        pytest.param([], {}, set(), set(), id="not-configured"),
    ],
)
async def test_coordinator_uses_tracked_cache_and_trackable_codes(
    hass: HomeAssistant,
    subentries: list[ConfigSubentryDataWithId],
    options: dict[str, list[str]],
    expected_cache_codes: set[str],
    expected_trackable_codes: set[str],
) -> None:
    """Test that tracked codes are passed to Geocaching settings."""
    config_entry = MockConfigEntry(
        title="1234AB 1",
        domain=DOMAIN,
        data={"id": "mock_user", "auth_implementation": DOMAIN},
        unique_id="mock_user",
        options=options,
        subentries_data=subentries,
    )
    config_entry.add_to_hass(hass)

    session = MagicMock()
    session.token = {"access_token": "mock-token"}
    status = GeocachingStatus()
    cache = GeocachingCache(reference_code="gc12345")
    trackable = GeocachingTrackable(reference_code=" tb12345 ")
    status.tracked_caches = [cache]
    status.trackables = {"original-key": trackable}
    original_trackables = status.trackables

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
            "homeassistant.components.geocaching.coordinator.GeocachingApi.update",
            new=AsyncMock(return_value=status),
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    settings = config_entry.runtime_data.geocaching._settings

    assert isinstance(settings, GeocachingSettings)
    assert settings.tracked_cache_codes == expected_cache_codes
    assert settings.tracked_trackable_codes == expected_trackable_codes
    assert config_entry.runtime_data.data.tracked_caches == {"GC12345": cache}
    assert config_entry.runtime_data.data.trackables == {"TB12345": trackable}
    assert status.tracked_caches == [cache]
    assert status.trackables is original_trackables
    assert status.trackables == {"original-key": trackable}
