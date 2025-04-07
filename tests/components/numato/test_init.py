"""Tests for the numato integration."""

from numato_gpio import NumatoGpioError
import pytest

from homeassistant.components import numato
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .common import NUMATO_CFG, mockup_raise, mockup_return


async def test_setup_no_devices(
    hass: HomeAssistant, numato_fixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test handling of an 'empty' discovery.

    Platform setups are expected to return after handling errors locally
    without raising.
    """
    monkeypatch.setattr(numato_fixture, "discover", mockup_return)
    assert await async_setup_component(hass, "numato", NUMATO_CFG)
    assert len(numato_fixture.devices) == 0


async def test_fail_setup_raising_discovery(
    hass: HomeAssistant, numato_fixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test handling of an exception during discovery.

    Setup shall return False.
    """
    monkeypatch.setattr(numato_fixture, "discover", mockup_raise)
    assert not await async_setup_component(hass, "numato", NUMATO_CFG)
    await hass.async_block_till_done()


async def test_hass_numato_api_wrong_port_directions(
    hass: HomeAssistant, numato_fixture
) -> None:
    """Test handling of wrong port directions.

    This won't happen in the current platform implementation but would raise
    in case of an introduced bug in the platforms.
    """
    numato_fixture.discover()
    api = numato.NumatoAPI()
    api.setup_output(0, 5)
    api.setup_input(0, 2)
    api.setup_output(0, 6)
    with pytest.raises(NumatoGpioError):
        api.read_adc_input(0, 5)  # adc_read from output
    with pytest.raises(NumatoGpioError):
        api.read_input(0, 6)  # read from output
    with pytest.raises(NumatoGpioError):
        api.write_output(0, 2, 1)  # write to input


async def test_hass_numato_api_errors(
    hass: HomeAssistant, numato_fixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test whether Home Assistant numato API (re-)raises errors."""
    numato_fixture.discover()
    monkeypatch.setattr(numato_fixture.devices[0], "setup", mockup_raise)
    monkeypatch.setattr(numato_fixture.devices[0], "adc_read", mockup_raise)
    monkeypatch.setattr(numato_fixture.devices[0], "read", mockup_raise)
    monkeypatch.setattr(numato_fixture.devices[0], "write", mockup_raise)
    api = numato.NumatoAPI()
    with pytest.raises(NumatoGpioError):
        api.setup_input(0, 5)
    with pytest.raises(NumatoGpioError):
        api.read_adc_input(0, 1)
    with pytest.raises(NumatoGpioError):
        api.read_input(0, 2)
    with pytest.raises(NumatoGpioError):
        api.write_output(0, 2, 1)


async def test_invalid_port_number(hass: HomeAssistant, numato_fixture, config) -> None:
    """Test validation of ADC port number type."""
    sensorports_cfg = config["numato"]["devices"][0]["sensors"]["ports"]
    port1_config = sensorports_cfg["1"]
    sensorports_cfg["one"] = port1_config
    del sensorports_cfg["1"]
    assert not await async_setup_component(hass, "numato", config)
    await hass.async_block_till_done()
    assert not numato_fixture.devices


async def test_too_low_adc_port_number(
    hass: HomeAssistant, numato_fixture, config
) -> None:
    """Test handling of failing component setup.

    Tries setting up an ADC on a port below (0) the allowed range.
    """

    sensorports_cfg = config["numato"]["devices"][0]["sensors"]["ports"]
    sensorports_cfg.update({0: {"name": "toolow"}})
    assert not await async_setup_component(hass, "numato", config)
    assert not numato_fixture.devices


async def test_too_high_adc_port_number(
    hass: HomeAssistant, numato_fixture, config
) -> None:
    """Test handling of failing component setup.

    Tries setting up an ADC on a port above (8) the allowed range.
    """
    sensorports_cfg = config["numato"]["devices"][0]["sensors"]["ports"]
    sensorports_cfg.update({8: {"name": "toohigh"}})
    assert not await async_setup_component(hass, "numato", config)
    assert not numato_fixture.devices


async def test_invalid_adc_range_value_type(
    hass: HomeAssistant, numato_fixture, config
) -> None:
    """Test validation of ADC range config's types.

    Replaces the source range beginning by a string.
    """
    sensorports_cfg = config["numato"]["devices"][0]["sensors"]["ports"]
    sensorports_cfg["1"]["source_range"][0] = "zero"
    assert not await async_setup_component(hass, "numato", config)
    assert not numato_fixture.devices


async def test_invalid_adc_source_range_length(
    hass: HomeAssistant, numato_fixture, config
) -> None:
    """Test validation of ADC range config's length.

    Adds an element to the source range.
    """
    sensorports_cfg = config["numato"]["devices"][0]["sensors"]["ports"]
    sensorports_cfg["1"]["source_range"].append(42)
    assert not await async_setup_component(hass, "numato", config)
    assert not numato_fixture.devices


async def test_invalid_adc_source_range_order(
    hass: HomeAssistant, numato_fixture, config
) -> None:
    """Test validation of ADC range config's order.

    Sets the source range to a decreasing [2, 1].
    """
    sensorports_cfg = config["numato"]["devices"][0]["sensors"]["ports"]
    sensorports_cfg["1"]["source_range"] = [2, 1]
    assert not await async_setup_component(hass, "numato", config)
    assert not numato_fixture.devices


async def test_invalid_adc_destination_range_value_type(
    hass: HomeAssistant, numato_fixture, config
) -> None:
    """Test validation of ADC range .

    Replaces the destination range beginning by a string.
    """
    sensorports_cfg = config["numato"]["devices"][0]["sensors"]["ports"]
    sensorports_cfg["1"]["destination_range"][0] = "zero"
    assert not await async_setup_component(hass, "numato", config)
    assert not numato_fixture.devices


async def test_invalid_adc_destination_range_length(
    hass: HomeAssistant, numato_fixture, config
) -> None:
    """Test validation of ADC range config's length.

    Adds an element to the destination range.
    """
    sensorports_cfg = config["numato"]["devices"][0]["sensors"]["ports"]
    sensorports_cfg["1"]["destination_range"].append(42)
    assert not await async_setup_component(hass, "numato", config)
    assert not numato_fixture.devices


async def test_invalid_adc_destination_range_order(
    hass: HomeAssistant, numato_fixture, config
) -> None:
    """Test validation of ADC range config's order.

    Sets the destination range to a decreasing [2, 1].
    """
    sensorports_cfg = config["numato"]["devices"][0]["sensors"]["ports"]
    sensorports_cfg["1"]["destination_range"] = [2, 1]
    assert not await async_setup_component(hass, "numato", config)
    assert not numato_fixture.devices
