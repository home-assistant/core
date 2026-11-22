"""Test the ADS component setup."""

from typing import Any
from unittest.mock import MagicMock

import pyads
import pytest

from homeassistant.components.ads.const import DOMAIN
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import ADS_CONFIG
from .const import AMS_NET_ID, IP_ADDRESS, PORT


@pytest.mark.parametrize(
    ("config", "expected_args"),
    [
        pytest.param(ADS_CONFIG, (AMS_NET_ID, PORT, IP_ADDRESS), id="ip_address"),
        pytest.param(
            {"device": AMS_NET_ID, "port": PORT},
            (AMS_NET_ID, PORT, None),
            id="no_ip_address",
        ),
    ],
)
async def test_setup(
    hass: HomeAssistant,
    mock_pyads_connection: MagicMock,
    config: dict[str, Any],
    expected_args: tuple[str, int, str | None],
) -> None:
    """Test the component opens the connection it was configured with."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: config})
    await hass.async_block_till_done()

    mock_pyads_connection.assert_called_once_with(*expected_args)
    mock_pyads_connection.return_value.open.assert_called_once()


@pytest.mark.parametrize(
    "config",
    [
        pytest.param({"port": PORT}, id="missing_device"),
        pytest.param({"device": AMS_NET_ID}, id="missing_port"),
        pytest.param({"device": AMS_NET_ID, "port": 70000}, id="invalid_port"),
    ],
)
async def test_invalid_config(
    hass: HomeAssistant, mock_pyads_connection: MagicMock, config: dict[str, Any]
) -> None:
    """Test an invalid configuration never opens a connection."""
    assert not await async_setup_component(hass, DOMAIN, {DOMAIN: config})
    await hass.async_block_till_done()

    mock_pyads_connection.assert_not_called()


async def test_setup_without_ads_section(
    hass: HomeAssistant,
    mock_pyads_connection: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the component fails to set up without its configuration section."""
    assert not await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    assert "Error during setup of component ads" in caplog.text
    mock_pyads_connection.assert_not_called()


async def test_setup_connection_error(
    hass: HomeAssistant,
    mock_pyads_connection: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a connection error leaves the component unset up."""
    mock_pyads_connection.return_value.open.side_effect = pyads.ADSError(err_code=1861)

    assert not await async_setup_component(hass, DOMAIN, {DOMAIN: ADS_CONFIG})
    await hass.async_block_till_done()

    assert (
        f"Could not connect to ADS host (netid={AMS_NET_ID}, ip={IP_ADDRESS}, "
        f"port={PORT})" in caplog.text
    )
    # The action is registered before the connection is attempted.
    assert hass.services.has_service(DOMAIN, "write_data_by_name")


@pytest.mark.usefixtures("setup_ads")
async def test_shutdown_on_stop(
    hass: HomeAssistant, mock_pyads_connection: MagicMock
) -> None:
    """Test the connection is closed when Home Assistant stops."""
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    mock_pyads_connection.return_value.close.assert_called_once()


@pytest.mark.usefixtures("setup_ads")
async def test_shutdown_close_error(
    hass: HomeAssistant,
    mock_pyads_connection: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a failure to close the connection is logged, not raised."""
    mock_pyads_connection.return_value.close.side_effect = pyads.ADSError(err_code=1864)

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    assert "ads-port not opened (1864)" in caplog.text
