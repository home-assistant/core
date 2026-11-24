"""Test the ADS hub's connection helpers."""

from unittest.mock import MagicMock

import pyads
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.ads.hub import async_get_hub, connect
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady

from .const import AMS_NET_ID, IP_ADDRESS, PORT


async def test_async_get_hub_not_loaded(hass: HomeAssistant) -> None:
    """Test a platform set up before the connection is told to retry."""
    with pytest.raises(PlatformNotReady):
        async_get_hub(hass)


@pytest.mark.usefixtures("mock_pyads_connection")
async def test_async_get_hub(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the hub of the loaded entry is returned."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert async_get_hub(hass) is mock_config_entry.runtime_data


@pytest.mark.parametrize(
    "configure_mock",
    [
        pytest.param(
            lambda mock: setattr(
                mock.return_value.read_state,
                "side_effect",
                pyads.ADSError(err_code=1861),
            ),
            id="timeout",
        ),
        pytest.param(
            lambda mock: setattr(mock.return_value.read_state, "return_value", None),
            id="port_closed",
        ),
    ],
)
def test_connect_closes_on_error(
    mock_pyads_connection: MagicMock, configure_mock
) -> None:
    """Test a connection the device does not answer on is closed again."""
    configure_mock(mock_pyads_connection)

    with pytest.raises(pyads.ADSError):
        connect(AMS_NET_ID, PORT, IP_ADDRESS)

    mock_pyads_connection.return_value.close.assert_called_once()
