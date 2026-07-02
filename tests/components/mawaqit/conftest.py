"""Fixtures for the Mawaqit integration tests."""

from __future__ import annotations

from collections.abc import Callable, Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.mawaqit.const import DOMAIN
from homeassistant.components.mawaqit.types import MawaqitMosqueData
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

MOCK_UUID = "aaaaa-bbbbb-cccccc-0000"
MOCK_TOKEN = "test-api-token"
MOCK_LATITUDE = 48.8566
MOCK_LONGITUDE = 2.3522

#: Six standard daily prayer times used throughout all calendar builders.
PRAYER_TIMES_ROW = ["05:30", "06:45", "12:30", "15:45", "18:30", "20:00"]

#: Five standard iqama offsets used throughout all iqama calendar builders.
IQAMA_OFFSET_TIMES_ROW = ["+10", "+15", "+10", "+5", "+10"]
IQAMA_ABSOLUTE_TIMES_ROW = ["05:45", "13:00", "16:00", "19:00", "21:00"]

MOCK_MOSQUE_DATA: dict[str, Any] = {
    "uuid": MOCK_UUID,
    "name": "Test Mosque",
    "announcements": [
        {"title": "Ramadan", "content": "Starts tomorrow"},
    ],
}

# Sentinel: distinguishes "caller did not supply a value" from explicit None.
_UNSET = object()


# ---------------------------------------------------------------------------
# Calendar builder helpers
# ---------------------------------------------------------------------------


def make_month_data(
    prayer_times: list[str] | None = None,
    days: range = range(1, 32),
) -> dict[str, list[str]]:
    """Return a single-month dict mapping day-string -> prayer-times list.

    Args:
        prayer_times: Row to assign to every day (default: 6 standard times).
        days:         Day numbers to include (default 1-31).

    """
    prayer_times = prayer_times or PRAYER_TIMES_ROW

    return {str(day): list(prayer_times) for day in days}


def make_iqama_month_data(
    iqama_times: list[str] | None = None,
    days: range = range(1, 32),
) -> dict[str, list[str]]:
    """Return a single-month iqama dict mapping day-string -> iqama list."""
    iqama_times = iqama_times or IQAMA_OFFSET_TIMES_ROW

    return {str(day): list(iqama_times) for day in days}


def build_prayer_data(
    *,
    iqama_enabled: bool = True,
    with_iqama_calendar: bool = True,
    jumua: str | None = "13:00",
    jumua2: str | None = "14:00",
    jumua3: str | None = None,
    fill_all_months: bool = True,
    active_month_index: int = 3,
) -> dict:
    """Build a complete prayer-data dict for coordinator / sensor tests.

    Args:
        iqama_enabled:       Sets the ``iqamaEnabled`` flag.
        with_iqama_calendar: When False the iqama calendar list is empty.
        jumua / jumua2 / jumua3: Friday prayer times; None omits the key.
        fill_all_months:     When True every month gets full day data.
                             When False only *active_month_index* has data.
        active_month_index:  0-based index of the active month (default 3 = April).

    """
    month_data = make_month_data()
    iqama_month_data = make_iqama_month_data()

    if fill_all_months:
        calendar: list[dict] = [month_data.copy() for _ in range(12)]
        iqama_calendar: list[dict] = [iqama_month_data.copy() for _ in range(12)]
    else:
        calendar = [{} for _ in range(12)]
        calendar[active_month_index] = month_data
        iqama_calendar = [{} for _ in range(12)]
        iqama_calendar[active_month_index] = iqama_month_data

    data: dict[str, Any] = {
        "uuid": MOCK_UUID,
        "name": "Test Mosque",
        "calendar": calendar,
        "iqamaCalendar": iqama_calendar if with_iqama_calendar else [],
        "iqamaEnabled": iqama_enabled,
        "timezone": "Europe/Paris",
        "shuruq": "06:45",
        "announcements": [{"title": "Ramadan", "content": "Starts tomorrow"}],
        **{
            key: value
            for key, value in (
                ("jumua", jumua),
                ("jumua2", jumua2),
                ("jumua3", jumua3),
            )
            if value is not None
        },
    }

    return data


# ---------------------------------------------------------------------------
# Core config-entry fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry for Mawaqit."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="MAWAQIT - Test Mosque",
        data={
            CONF_API_KEY: MOCK_TOKEN,
            "uuid": MOCK_UUID,
            CONF_LATITUDE: MOCK_LATITUDE,
            CONF_LONGITUDE: MOCK_LONGITUDE,
        },
        unique_id="mawaqit_unique",
    )


@pytest.fixture
def mock_config_entry_mawaqit() -> MockConfigEntry:
    """Mock a config entry used by config-flow reconfigure tests."""
    return MockConfigEntry(
        version=10,
        minor_version=1,
        domain=DOMAIN,
        title="MAWAQIT - Mosque1",
        data={
            "api_key": "TOKEN",
            "uuid": "aaaaa-bbbbb-cccccc-0000",
            "latitude": 32.87336,
            "longitude": -117.22743,
        },
        source=config_entries.SOURCE_USER,
        unique_id="84fce612f5b8",
    )


# ---------------------------------------------------------------------------
# Mosque search fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_mosques_search_api_raw() -> list[dict]:
    """Provide raw API dicts for neighbourhood mosque search results."""
    return [
        {
            "uuid": "aaaaa-bbbbb-cccccc-0000",
            "name": "Mosque1",
            "type": "MOSQUE",
            "slug": "1-mosque",
            "latitude": 48,
            "longitude": 1,
            "jumua": None,
            "proximity": 1744,
            "label": "Mosque1-label",
            "localisation": "aaaaa bbbbb cccccc",
        },
        {
            "uuid": "bbbbb-cccccc-ddddd-0000",
            "name": "Mosque2-label",
            "type": "MOSQUE",
            "slug": "2-mosque",
            "latitude": 47,
            "longitude": 1,
            "jumua": None,
            "proximity": 20000,
            "label": "Mosque2-label",
            "localisation": "bbbbb cccccc ddddd",
        },
        {
            "uuid": "bbbbb-cccccc-ddddd-0001",
            "name": "Mosque3",
            "type": "MOSQUE",
            "slug": "2-mosque",
            "latitude": 47,
            "longitude": 1,
            "jumua": None,
            "proximity": 20000,
            "label": "Mosque3-label",
            "localisation": "bbbbb cccccc ddddd",
        },
    ]


@pytest.fixture
def mock_mosques_search_api_wrapper(
    mock_mosques_search_api_raw: list[dict],
) -> list[MawaqitMosqueData]:
    """Return ``MawaqitMosqueData`` objects built from the raw API fixture."""
    return [
        MawaqitMosqueData.from_dict(mosque) for mosque in mock_mosques_search_api_raw
    ]


# ---------------------------------------------------------------------------
# Prayer / mosque data fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_prayer_data() -> dict:
    """Return a complete mock prayer-time dict with all 12 months filled."""
    return build_prayer_data()


@pytest.fixture
def mock_mosque_data() -> dict:
    """Return mock mosque detail data."""
    return dict(MOCK_MOSQUE_DATA)


# ---------------------------------------------------------------------------
# Mawaqit client mock
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_mawaqit_client() -> Generator[MagicMock]:
    """Return a mocked AsyncMawaqitClient."""
    with patch(
        "homeassistant.components.mawaqit.mawaqit_wrapper.AsyncMawaqitClient",
        autospec=True,
    ) as client_mock:
        client = client_mock.return_value
        client.login = AsyncMock()
        client.close = AsyncMock()
        client.get_api_token = AsyncMock(return_value=MOCK_TOKEN)
        client.all_mosques_neighborhood = AsyncMock(return_value=[])
        client.fetch_mosques_by_keyword = AsyncMock(return_value=[])
        client.fetch_prayer_times = AsyncMock(return_value={})
        client.fetch_mosque_by_id = AsyncMock(return_value={})
        yield client


# ---------------------------------------------------------------------------
# Integration setup helper fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def setup_mawaqit_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> Callable:
    """Return an async helper that sets up the Mawaqit integration.

    Usage::

        # Use defaults (MOCK_MOSQUE_DATA + build_prayer_data())
        await setup_mawaqit_integration()

        # Override data
        await setup_mawaqit_integration(mosque_data={"name": "Other"})

        # Inject an explicit None (coordinator receives no data -> SETUP_RETRY)
        await setup_mawaqit_integration(mosque_data=None)

        # Inject an exception
        await setup_mawaqit_integration(prayer_side_effect=BadCredentialsException)

    Passing ``mosque_data=None`` (or ``prayer_data=None``) is intentional and
    causes the mock to return ``None``, which triggers ``UpdateFailed``.
    When a parameter is *omitted entirely* the fixture supplies sensible defaults.
    """

    async def _setup(
        mosque_data: dict | None = _UNSET,
        prayer_data: dict | None = _UNSET,
        mosque_side_effect: type[Exception] | None = None,
        prayer_side_effect: type[Exception] | None = None,
    ) -> None:
        resolved_mosque = (
            dict(MOCK_MOSQUE_DATA) if mosque_data is _UNSET else mosque_data
        )
        resolved_prayer = build_prayer_data() if prayer_data is _UNSET else prayer_data

        mock_config_entry.add_to_hass(hass)

        with (
            patch(
                "homeassistant.components.mawaqit.mawaqit_wrapper.fetch_mosque_by_id",
                new_callable=AsyncMock,
                return_value=resolved_mosque,
                side_effect=mosque_side_effect,
            ),
            patch(
                "homeassistant.components.mawaqit.mawaqit_wrapper.fetch_prayer_times",
                new_callable=AsyncMock,
                return_value=resolved_prayer,
                side_effect=prayer_side_effect,
            ),
        ):
            await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

    return _setup


# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_setup_entry() -> Generator[None]:
    """Mock setting up a config entry (skips real coordinator setup)."""
    with patch("homeassistant.components.mawaqit.async_setup_entry", return_value=True):
        yield
