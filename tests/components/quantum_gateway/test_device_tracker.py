"""Tests for the quantum_gateway device tracker."""

from unittest import mock

import pytest
from requests import RequestException

from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
import homeassistant.components.quantum_gateway.device_tracker as quantum_gateway_device_tracker
from homeassistant.const import CONF_PASSWORD, CONF_PLATFORM
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.components.device_tracker.test_init import mock_yaml_devices  # noqa: F401


@pytest.fixture
def mocked_quantum_gateway_scanner():
    """Mock for pyopnense.diagnostics."""
    with mock.patch.object(
        quantum_gateway_device_tracker, "QuantumGatewayScanner"
    ) as mocked_scanner:
        yield mocked_scanner


@pytest.mark.usefixtures("yaml_devices")
async def test_get_scanner(hass: HomeAssistant, mocked_quantum_gateway_scanner) -> None:
    """Test creating a quantum gateway scanner."""
    connected_devices = {
        "ff:ff:ff:ff:ff:ff": "",
        "ff:ff:ff:ff:ff:fe": "desktop",
    }

    mocked_quantum_gateway_scanner.configure_mock(
        return_value=mock.Mock(
            **{
                "success_init": True,
                "scan_devices.return_value": list(connected_devices.keys()),
                "get_device_name.side_effect": connected_devices.get,
            }
        )
    )

    result = await async_setup_component(
        hass,
        DEVICE_TRACKER_DOMAIN,
        {
            DEVICE_TRACKER_DOMAIN: {
                CONF_PLATFORM: "quantum_gateway",
                CONF_PASSWORD: "fake_password",
            }
        },
    )
    await hass.async_block_till_done()
    assert result

    device_1 = hass.states.get("device_tracker.desktop")
    assert device_1 is not None
    assert device_1.state == "home"

    device_2 = hass.states.get("device_tracker.ff_ff_ff_ff_ff_ff")
    assert device_2 is not None
    assert device_2.state == "home"


@pytest.mark.usefixtures("yaml_devices")
async def test_get_scanner_error(
    hass: HomeAssistant, mocked_quantum_gateway_scanner
) -> None:
    """Test failure when creating a quantum gateway scanner."""

    mocked_quantum_gateway_scanner.configure_mock(side_effect=RequestException("Error"))

    result = await async_setup_component(
        hass,
        DEVICE_TRACKER_DOMAIN,
        {
            DEVICE_TRACKER_DOMAIN: {
                CONF_PLATFORM: "quantum_gateway",
                CONF_PASSWORD: "fake_password",
            }
        },
    )
    await hass.async_block_till_done()
    assert result

    assert "quantum_gateway.device_tracker" not in hass.config.components


@pytest.mark.usefixtures("yaml_devices")
async def test_scan_devices_error(
    hass: HomeAssistant, mocked_quantum_gateway_scanner
) -> None:
    """Test failure when scanning devices."""
    mocked_quantum_gateway_scanner.configure_mock(
        return_value=mock.Mock(
            **{
                "success_init": True,
                "scan_devices.side_effect": RequestException("Error"),
            }
        )
    )

    result = await async_setup_component(
        hass,
        DEVICE_TRACKER_DOMAIN,
        {
            DEVICE_TRACKER_DOMAIN: {
                CONF_PLATFORM: "quantum_gateway",
                CONF_PASSWORD: "fake_password",
            }
        },
    )
    await hass.async_block_till_done()
    assert result

    assert "quantum_gateway.device_tracker" in hass.config.components

    device_1 = hass.states.get("device_tracker.desktop")
    assert device_1 is None

    device_2 = hass.states.get("device_tracker.ff_ff_ff_ff_ff_ff")
    assert device_2 is None
