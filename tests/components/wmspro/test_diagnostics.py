"""Test the wmspro diagnostics."""

from unittest.mock import AsyncMock

import pytest
from syrupy import SnapshotAssertion

from homeassistant.core import HomeAssistant

from . import setup_config_entry

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


@pytest.mark.parametrize(
    ("mock_hub_configuration"),
    [
        ("mock_hub_configuration_prod_awning_dimmer"),
        ("mock_hub_configuration_prod_roller_shutter"),
    ],
)
async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_hub_ping: AsyncMock,
    mock_hub_configuration: AsyncMock,
    mock_dest_refresh: AsyncMock,
    snapshot: SnapshotAssertion,
    request: pytest.FixtureRequest,
) -> None:
    """Test that a config entry can be loaded with DeviceConfig."""
    mock_hub_configuration = request.getfixturevalue(mock_hub_configuration)

    assert await setup_config_entry(hass, mock_config_entry)
    assert len(mock_hub_ping.mock_calls) == 1
    assert len(mock_hub_configuration.mock_calls) == 1
    assert len(mock_dest_refresh.mock_calls) > 0

    result = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )
    assert result == snapshot
