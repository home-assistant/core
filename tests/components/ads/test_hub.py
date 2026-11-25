"""Test the ADS hub's connection helpers."""

from unittest.mock import MagicMock, patch

import pyads
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.ads.const import DOMAIN
from homeassistant.components.ads.hub import async_get_hub, connect
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import CONF_DEVICE, CONF_PORT, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.setup import async_setup_component

from . import MockAdsDevice, setup_ads_platform
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


async def test_platform_waits_for_the_import(
    hass: HomeAssistant,
    mock_ads_device: MockAdsDevice,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a YAML platform waits for the imported entry instead of retrying."""
    mock_ads_device.values["GVL.pump"] = b"\x01"

    assert await setup_ads_platform(
        hass,
        mock_ads_device,
        SWITCH_DOMAIN,
        {"adsvar": "GVL.pump", "name": "Pump"},
    )

    assert hass.states.get("switch.pump").state == STATE_ON
    assert "not ready yet" not in caplog.text


async def test_platform_gives_up_without_an_entry(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test a YAML platform retries on its own when no entry ever sets up."""
    with patch("homeassistant.components.ads.hub.HUB_WAIT_TIMEOUT", 0):
        assert await async_setup_component(
            hass,
            SWITCH_DOMAIN,
            {
                DOMAIN: {CONF_DEVICE: "bad", CONF_PORT: PORT},
                SWITCH_DOMAIN: {
                    "platform": DOMAIN,
                    "adsvar": "GVL.pump",
                    "name": "Pump",
                },
            },
        )
        await hass.async_block_till_done()

    assert hass.states.get("switch.pump") is None
    assert "The ADS connection is not set up" in caplog.text
