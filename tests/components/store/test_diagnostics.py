"""Tests for the Community store diagnostics."""

from http import HTTPStatus

import pytest
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.core import HomeAssistant

from . import mocked_response
from .conftest import StoreResponses
from .const import TOKEN

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
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


@pytest.mark.usefixtures("stored_repositories", "init_integration")
async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the diagnostics of a set up store."""
    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert TOKEN not in str(diagnostics)

    # The categories and the repositories come out of sets, so they need an
    # order before they can be compared
    diagnostics["store"]["categories"] = sorted(diagnostics["store"]["categories"])
    diagnostics["custom_repositories"].sort()
    diagnostics["repositories"].sort(key=lambda repo: repo["data"]["full_name"])

    assert diagnostics == snapshot(exclude=EXCLUDED)


@pytest.mark.usefixtures("init_integration")
async def test_diagnostics_without_a_rate_limit(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    response_mocker: StoreResponses,
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
