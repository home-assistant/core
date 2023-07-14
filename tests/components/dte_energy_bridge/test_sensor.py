"""The tests for the DTE Energy Bridge."""
import requests_mock

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

DTE_ENERGY_BRIDGE_CONFIG = {"platform": "dte_energy_bridge", "ip": "192.168.1.1"}


async def test_setup_with_config(hass: HomeAssistant) -> None:
    """Test the platform setup with configuration."""
    assert await async_setup_component(
        hass, "sensor", {"dte_energy_bridge": DTE_ENERGY_BRIDGE_CONFIG}
    )
    await hass.async_block_till_done()


async def test_setup_correct_reading(hass: HomeAssistant) -> None:
    """Test DTE Energy bridge returns a correct value."""
    with requests_mock.Mocker() as mock_req:
        mock_req.get(
            "http://{}/instantaneousdemand".format(DTE_ENERGY_BRIDGE_CONFIG["ip"]),
            text=".411 kW",
        )
        assert await async_setup_component(
            hass, "sensor", {"sensor": DTE_ENERGY_BRIDGE_CONFIG}
        )
        await hass.async_block_till_done()
    assert hass.states.get("sensor.current_energy_usage").state == "0.411"


async def test_setup_incorrect_units_reading(hass: HomeAssistant) -> None:
    """Test DTE Energy bridge handles a value with incorrect units."""
    with requests_mock.Mocker() as mock_req:
        mock_req.get(
            "http://{}/instantaneousdemand".format(DTE_ENERGY_BRIDGE_CONFIG["ip"]),
            text="411 kW",
        )
        assert await async_setup_component(
            hass, "sensor", {"sensor": DTE_ENERGY_BRIDGE_CONFIG}
        )
        await hass.async_block_till_done()
    assert hass.states.get("sensor.current_energy_usage").state == "0.411"


async def test_setup_bad_format_reading(hass: HomeAssistant) -> None:
    """Test DTE Energy bridge handles an invalid value."""
    with requests_mock.Mocker() as mock_req:
        mock_req.get(
            "http://{}/instantaneousdemand".format(DTE_ENERGY_BRIDGE_CONFIG["ip"]),
            text="411",
        )
        assert await async_setup_component(
            hass, "sensor", {"sensor": DTE_ENERGY_BRIDGE_CONFIG}
        )
        await hass.async_block_till_done()
    assert hass.states.get("sensor.current_energy_usage").state == "unknown"
