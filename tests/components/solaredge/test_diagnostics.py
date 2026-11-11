"""Tests for the SolarEdge diagnostics."""

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from . import setup_integration


@pytest.mark.usefixtures("recorder_mock", "solaredge_api", "solaredge_web_api")
@pytest.mark.parametrize(
    "config_entry_fixture",
    [
        pytest.param("mock_config_entry", id="api_key"),
        pytest.param("mock_config_entry_web_login", id="web_login"),
    ],
)
async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    request: pytest.FixtureRequest,
    config_entry_fixture: str,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    config_entry: MockConfigEntry = request.getfixturevalue(config_entry_fixture)
    await setup_integration(hass, config_entry)

    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
        == snapshot
    )
