"""Tests for the Geocaching integration."""

from collections.abc import Sequence
import datetime as dt
from unittest.mock import MagicMock

from geocachingapi.models import GeocachingCache, GeocachingStatus
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.geocaching.const import (
    DOMAIN,
    SUBENTRY_TYPE_TRACKED_CACHE,
)
from homeassistant.config_entries import ConfigSubentryDataWithId
from homeassistant.const import CONF_CODE
from homeassistant.core import HomeAssistant

CLIENT_ID = "1234"
CLIENT_SECRET = "5678"
REDIRECT_URI = "https://example.com/auth/external/callback"

DEFAULT_USERNAME = "mock_user"
DEFAULT_REFERENCE_CODE = "PR12345"
DEFAULT_CACHE_CODE = "GC12345"


def create_tracked_cache_subentry(
    code: str, *, subentry_id: str | None = None
) -> ConfigSubentryDataWithId:
    """Build a tracked cache subentry for a config entry."""
    return ConfigSubentryDataWithId(
        data={CONF_CODE: code},
        subentry_type=SUBENTRY_TYPE_TRACKED_CACHE,
        title=code,
        unique_id=code,
        subentry_id=subentry_id or f"{code}-subentry",
    )


def create_config_entry(
    *,
    username: str = DEFAULT_USERNAME,
    subentries: Sequence[ConfigSubentryDataWithId] = (),
) -> MockConfigEntry:
    """Build a mocked Geocaching config entry, optionally tracking caches."""
    return MockConfigEntry(
        title=username,
        domain=DOMAIN,
        data={"id": username, "auth_implementation": DOMAIN},
        unique_id=username,
        subentries_data=list(subentries),
    )


def create_cache(
    *,
    reference_code: str = DEFAULT_CACHE_CODE,
    name: str = "Test cache",
    owner_username: str = "CacheOwner",
    favorite_points: int | None = 10,
    found_date_time: dt.datetime | None = None,
    hidden_date: dt.date | None = None,
) -> GeocachingCache:
    """Build a GeocachingCache as the API would return it."""
    owner = MagicMock()
    owner.username = owner_username
    return GeocachingCache(
        reference_code=reference_code,
        name=name,
        owner=owner,
        favorite_points=favorite_points,
        found_date_time=found_date_time,
        hidden_date=hidden_date,
    )


def create_status(
    *,
    username: str = DEFAULT_USERNAME,
    reference_code: str = DEFAULT_REFERENCE_CODE,
    find_count: int | None = None,
    tracked_caches: Sequence[GeocachingCache] = (),
) -> GeocachingStatus:
    """Build a GeocachingStatus as the API would return it."""
    status = GeocachingStatus()
    status.user.username = username
    status.user.reference_code = reference_code
    status.user.find_count = find_count
    status.tracked_caches = list(tracked_caches)
    return status


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Add a config entry to hass and set it up.

    Requires the ``mock_oauth_session`` and ``mock_geocaching_api`` fixtures
    to already be active.
    """
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
