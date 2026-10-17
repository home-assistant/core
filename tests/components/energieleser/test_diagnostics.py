"""Test energieleser diagnostics."""

from unittest.mock import AsyncMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


@pytest.mark.parametrize(
    ("device_fixture", "config_entry_fixture"),
    [
        pytest.param(
            "mock_stromleser_device", "mock_stromleser_config_entry", id="stromleser"
        ),
        pytest.param(
            "mock_gasleser_device", "mock_gasleser_config_entry", id="gasleser"
        ),
        pytest.param(
            "mock_waermeleser_device",
            "mock_waermeleser_config_entry",
            id="waermeleser",
        ),
        pytest.param(
            "mock_wasserleser_device",
            "mock_wasserleser_config_entry",
            id="wasserleser",
        ),
    ],
)
async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_energieleser_client: AsyncMock,
    device_fixture: str,
    config_entry_fixture: str,
    request: pytest.FixtureRequest,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    device = request.getfixturevalue(device_fixture)
    config_entry = request.getfixturevalue(config_entry_fixture)

    mock_energieleser_client.get_device.return_value = device
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)

    assert result == snapshot
