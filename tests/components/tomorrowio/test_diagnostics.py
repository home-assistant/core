"""Tests for the Tomorrow.io diagnostics."""

from typing import Any
from unittest.mock import AsyncMock

import pytest
from pytest_homeassistant.common import load_json_object_fixture
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import make_location_subentry_data, make_v2_config_entry


@pytest.mark.parametrize(
    "api_response",
    [
        pytest.param(load_json_object_fixture("v4.json", "tomorrowio"), id="full"),
        pytest.param({"current": {}, "forecasts": {}}, id="empty"),
    ],
)
async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    tomorrowio_config_entry_update: AsyncMock,
    snapshot: SnapshotAssertion,
    api_response: dict[str, Any],
) -> None:
    """Test diagnostics."""
    tomorrowio_config_entry_update.return_value = api_response
    config_entry = make_v2_config_entry(
        subentries_data=[
            make_location_subentry_data(),
            make_location_subentry_data(
                location={"latitude": 52.37, "longitude": 4.89},
                name="My secret home",
                timestep=5,
                subentry_id="01JZZZZZZZZZZZZZZZZZZZZZZZ",
            ),
        ]
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
        == snapshot
    )
