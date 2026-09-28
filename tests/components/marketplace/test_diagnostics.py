"""Tests for the Marketplace diagnostics."""

from http import HTTPStatus

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.config_entries import SOURCE_SYSTEM
from homeassistant.core import HomeAssistant

from . import mocked_response
from .conftest import MarketplaceResponses
from .const import TOKEN, WARNING_ACCEPTANCE

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator

# The entry keys that change between runs, plus the Home Assistant version.
EXCLUDED = props(
    "created_at",
    "discovery_keys",
    "entry_id",
    "minor_version",
    "modified_at",
    "subentries",
    "version",
)


@pytest.fixture(autouse=True)
def frozen_after_acceptance(freezer: FrozenDateTimeFactory) -> None:
    """Freeze the clock a day after the warning was accepted.

    Before anything signs in, so the access tokens are valid at that instant.
    """
    freezer.move_to("2026-09-02T12:00:00+00:00")


@pytest.mark.usefixtures("stored_repositories", "init_integration")
async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the diagnostics of a set up Marketplace."""
    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert TOKEN not in str(diagnostics)

    # The categories and the repositories come out of sets, so they need an
    # order before they can be compared
    diagnostics["marketplace"]["categories"] = sorted(
        diagnostics["marketplace"]["categories"]
    )
    diagnostics["custom_repositories"].sort()
    diagnostics["repositories"].sort(key=lambda repo: repo["data"]["full_name"])

    assert diagnostics == snapshot(exclude=EXCLUDED)


@pytest.mark.usefixtures("init_integration")
async def test_diagnostics_without_a_rate_limit(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    response_mocker: MarketplaceResponses,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the diagnostics when the rate limit can not be read."""
    response_mocker.add(
        "https://api.github.com/rate_limit",
        mocked_response(
            "https://api.github.com/rate_limit",
            status=HTTPStatus.BAD_REQUEST,
            content=b"Something went wrong",
        ),
    )

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert diagnostics["rate_limit"] == snapshot


@pytest.mark.parametrize("github_token", [None])
@pytest.mark.usefixtures("init_integration")
async def test_diagnostics_without_github(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the diagnostics leave the anonymous rate limit alone."""
    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert diagnostics["marketplace"]["github_connected"] is False
    assert "rate_limit" not in diagnostics
    assert not [
        url for _, url, _, _ in aioclient_mock.mock_calls if url.path == "/rate_limit"
    ]


@pytest.mark.parametrize("config_entry_source", [SOURCE_SYSTEM])
@pytest.mark.parametrize("warning_accepted", [None])
@pytest.mark.usefixtures("init_integration")
async def test_diagnostics_without_accepted_warning(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the diagnostics tell the warning has not been accepted yet."""
    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert diagnostics["marketplace"]["warning_accepted_users"] == 0
    assert diagnostics["marketplace"]["warning_last_accepted_at"] is None
    assert diagnostics["marketplace"]["warning_reminders_due"] == 0


@pytest.mark.parametrize(
    "warning_accepted",
    [
        {
            "abc": {"version": 1, "accepted_at": "2026-05-01T12:00:00+00:00"},
            "def": WARNING_ACCEPTANCE,
            "ghi": {"version": 0, "accepted_at": "2026-09-02T00:00:00+00:00"},
        }
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_diagnostics_of_several_acceptances(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the diagnostics sum the acceptances up without telling who accepted."""
    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    # An acceptance of an older version of the warning no longer counts
    assert diagnostics["marketplace"]["warning_accepted_users"] == 2
    assert (
        diagnostics["marketplace"]["warning_last_accepted_at"]
        == WARNING_ACCEPTANCE["accepted_at"]
    )
    assert diagnostics["marketplace"]["warning_reminders_due"] == 1
    assert diagnostics["entry"]["data"]["warning_accepted"] == "**REDACTED**"
