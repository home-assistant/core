"""Test the my-PV diagnostics."""

from unittest.mock import AsyncMock, Mock

from my_pv.exceptions import MyPVConnectionError
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.diagnostics import REDACTED
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from . import setup_integration


@pytest.mark.usefixtures("mock_my_pv_client")
async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics."""
    await setup_integration(hass, mock_config_entry)

    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)
        == snapshot
    )


async def test_diagnostics_disconnected(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_my_pv_client: AsyncMock,
) -> None:
    """Test diagnostics when the device disconnected after setup."""
    await setup_integration(hass, mock_config_entry)

    # Reading values from a disconnected device raises an error
    mock_my_pv_client.connected = False
    mock_my_pv_client.get_setup_value = Mock(side_effect=MyPVConnectionError)
    mock_my_pv_client.get_data_value = Mock(side_effect=MyPVConnectionError)

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    mock_my_pv_client.get_setup_value.assert_not_called()
    mock_my_pv_client.get_data_value.assert_not_called()

    assert "setup_values" not in diagnostics
    assert "data_values" not in diagnostics

    assert diagnostics["entry_data"][CONF_HOST] == REDACTED
    assert diagnostics["entry_data"][CONF_PASSWORD] == REDACTED
    assert diagnostics["device"]["serial_number"] == REDACTED
    assert diagnostics["device"]["mac_address"] == REDACTED
    assert diagnostics["device"]["serial_number_prefix"] == "160150"
    assert diagnostics["device"]["connected"] is False
    assert diagnostics["setup_configurations"]
    assert diagnostics["data_configurations"]
