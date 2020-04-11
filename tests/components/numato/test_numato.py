"""Tests for the numato integration."""
from copy import copy, deepcopy
import logging

from numato_gpio import NumatoGpioError
import pytest

import homeassistant.components.numato as numato
from homeassistant.setup import async_setup_component

from . import numato_mock

from tests.components.switch.common import async_turn_off, async_turn_on

BINARY_SENSOR_CFG = {
    "binary_sensor": {
        "platform": "numato",
        "devices": [
            {
                "id": 0,
                "invert_logic": False,
                "ports": {
                    "2": "numato_binary_sensor_mock_port2",
                    "3": "numato_binary_sensor_mock_port3",
                    "4": "numato_binary_sensor_mock_port4",
                },
            }
        ],
    }
}

SENSOR_CFG = {
    "sensor": {
        "platform": "numato",
        "devices": [
            {
                "id": 0,
                "ports": {
                    "1": {
                        "name": "numato_adc_mock_port1",
                        "source_range": [100, 1023],
                        "destination_range": [0, 10],
                        "unit": "mocks",
                    }
                },
            }
        ],
    }
}

SWITCH_CFG = {
    "switch": {
        "platform": "numato",
        "devices": [
            {
                "id": 0,
                "invert_logic": False,
                "ports": {
                    "5": "numato_switch_mock_port5",
                    "6": "numato_switch_mock_port6",
                },
            }
        ],
    }
}


@pytest.fixture
def numato_fixture():
    """Inject the numato mockup into numato homeassistant module."""
    module_mock = copy(numato_mock.NumatoModuleMock)
    numato.__dict__["gpio"] = module_mock
    numato.PORTS_IN_USE.clear()
    return module_mock


async def test_failing_setup(hass, numato_fixture, monkeypatch):
    """Test that failing setup doesn't raise, but devices list empty."""
    monkeypatch.setattr(numato_fixture, "inject_error", True)
    assert await async_setup_component(hass, "numato", {})
    assert len(numato_fixture.devices) == 0


async def test_failing_component_setup(hass, numato_fixture, caplog, monkeypatch):
    """Test handling of failing component setup."""
    assert await async_setup_component(hass, "numato", {})
    # setup with failing ports (handled by component setup, no exceptions)
    monkeypatch.setattr(numato_fixture, "inject_error", True)
    with caplog.at_level(logging.ERROR):
        caplog.clear()
        assert await async_setup_component(hass, "binary_sensor", BINARY_SENSOR_CFG)
        assert len(caplog.records) == 3
        assert await async_setup_component(hass, "sensor", SENSOR_CFG)
        assert len(caplog.records) == 4
        assert await async_setup_component(hass, "switch", SWITCH_CFG)
        assert len(caplog.records) == 6


async def test_regular_hass_operations(hass, numato_fixture, monkeypatch):
    """Test regular operations from within Home Assistant."""
    assert await async_setup_component(hass, "numato", {})
    assert await async_setup_component(hass, "binary_sensor", BINARY_SENSOR_CFG)
    assert await async_setup_component(hass, "sensor", SENSOR_CFG)
    assert await async_setup_component(hass, "switch", SWITCH_CFG)

    await async_turn_on(hass, "switch.numato_switch_mock_port5")
    assert numato_fixture.devices[0].values[5] == 1
    await async_turn_on(hass, "switch.numato_switch_mock_port6")
    assert numato_fixture.devices[0].values[6] == 1
    await async_turn_off(hass, "switch.numato_switch_mock_port5")
    assert numato_fixture.devices[0].values[5] == 0
    await async_turn_off(hass, "switch.numato_switch_mock_port6")
    assert numato_fixture.devices[0].values[6] == 0

    numato_fixture.devices[0].mockup_inject_notification(2, 1)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.numato_binary_sensor_mock_port2")
    assert state.state == "on"


async def test_hass_numato_api(hass, numato_fixture):
    """Test regular device access."""
    assert await async_setup_component(hass, "numato", {})

    # regular operations
    numato.read_adc_input(0, 1)
    numato.read_input(0, 2)
    numato.write_output(0, 2, 1)

    def gen_callback(expected_port, expected_value):
        def cb_mockup(port, value):
            assert port == expected_port
            assert value == expected_value

        return cb_mockup

    numato.edge_detect(0, 2, gen_callback(2, 1))
    numato_fixture.devices[0].mockup_inject_notification(2, 1)
    numato.edge_detect(0, 2, gen_callback(2, 0))
    numato_fixture.devices[0].mockup_inject_notification(2, 0)


async def test_hass_numato_api_irregular_unhandled(hass, numato_fixture):
    """Test irregular, unhandled operations."""
    numato.read_adc_input(0, 5)  # port 5 configured as output
    numato.read_input(0, 6)  # port 6 configured as output
    numato.write_output(0, 2, 1)  # port 2 configured as input


async def test_hass_numato_api_errors(hass, numato_fixture, monkeypatch):
    """Test whether Home Assistant numato API (re-)raises errors."""
    monkeypatch.setattr(numato_fixture, "inject_error", True)
    with pytest.raises(NumatoGpioError):
        numato.setup_input(0, 5)
        numato.read_adc_input(0, 1)
        numato.read_input(0, 2)
        numato.write_output(0, 2, 1)


async def test_invalid_port_number(hass, numato_fixture):
    """Test validation of ADC port number type."""
    assert await async_setup_component(hass, "numato", {})
    sens_cfg = deepcopy(SENSOR_CFG)
    port1_config = sens_cfg["sensor"]["devices"][0]["ports"]["1"]
    sens_cfg["sensor"]["devices"][0]["ports"]["one"] = port1_config
    del sens_cfg["sensor"]["devices"][0]["ports"]["1"]
    assert await async_setup_component(hass, "sensor", sens_cfg)
    assert 1 not in numato_fixture.devices[0].ports


async def test_invalid_adc_port_number(hass, numato_fixture):
    """Test handling of failing component setup.

    Tries setting up an ADC on a port below (0) and above (8) the allowed
    range.
    """
    assert await async_setup_component(hass, "numato", {})
    sens_cfg = deepcopy(SENSOR_CFG)
    sens_cfg["sensor"]["devices"][0]["ports"].update({0: {"name": "toolow"}})
    assert await async_setup_component(hass, "sensor", sens_cfg)
    assert 0 not in numato_fixture.devices[0].ports

    sens_cfg = deepcopy(SENSOR_CFG)
    sens_cfg["sensor"]["devices"][0]["ports"].update({8: {"name": "toohigh"}})
    assert await async_setup_component(hass, "sensor", sens_cfg)
    assert 8 not in numato_fixture.devices[0].ports


async def test_invalid_adc_range_value_type(hass, numato_fixture):
    """Test validation of ADC range config's types.

    Replaces the source range beginning by a string.
    """
    assert await async_setup_component(hass, "numato", {})
    sens_cfg = deepcopy(SENSOR_CFG)
    sens_cfg["sensor"]["devices"][0]["ports"]["1"]["source_range"][0] = "zero"
    assert await async_setup_component(hass, "sensor", sens_cfg)
    assert 1 not in numato_fixture.devices[0].ports


async def test_invalid_adc_source_range_length(hass, numato_fixture):
    """Test validation of ADC range config's length.

    Adds an element to the source range.
    """
    assert await async_setup_component(hass, "numato", {})
    sens_cfg = deepcopy(SENSOR_CFG)
    sens_cfg["sensor"]["devices"][0]["ports"]["1"]["source_range"].append(42)
    assert await async_setup_component(hass, "sensor", sens_cfg)
    assert 1 not in numato_fixture.devices[0].ports


async def test_invalid_adc_source_range_order(hass, numato_fixture):
    """Test validation of ADC range config's order.

    Sets the source range to a decreasing [2, 1].
    """
    assert await async_setup_component(hass, "numato", {})
    sens_cfg = deepcopy(SENSOR_CFG)
    sens_cfg["sensor"]["devices"][0]["ports"]["1"]["source_range"] = [2, 1]
    assert await async_setup_component(hass, "sensor", sens_cfg)
    assert 1 not in numato_fixture.devices[0].ports


async def test_invalid_adc_destination_range_value_type(hass, numato_fixture):
    """Test validation of ADC range .

    Replaces the destination range beginning by a string.
    """
    assert await async_setup_component(hass, "numato", {})
    sens_cfg = deepcopy(SENSOR_CFG)
    sens_cfg["sensor"]["devices"][0]["ports"]["1"]["destination_range"][0] = "zero"
    assert await async_setup_component(hass, "sensor", sens_cfg)
    assert 1 not in numato_fixture.devices[0].ports


async def test_invalid_adc_destination_range_length(hass, numato_fixture):
    """Test validation of ADC range config's length.

    Adds an element to the destination range.
    """
    assert await async_setup_component(hass, "numato", {})
    sens_cfg = deepcopy(SENSOR_CFG)
    sens_cfg["sensor"]["devices"][0]["ports"]["1"]["destination_range"].append(42)
    assert await async_setup_component(hass, "sensor", sens_cfg)
    assert 1 not in numato_fixture.devices[0].ports


async def test_invalid_adc_destination_range_order(hass, numato_fixture):
    """Test validation of ADC range config's order.

    Sets the destination range to a decreasing [2, 1].
    """
    assert await async_setup_component(hass, "numato", {})
    sens_cfg = deepcopy(SENSOR_CFG)
    sens_cfg["sensor"]["devices"][0]["ports"]["1"]["destination_range"] = [2, 1]
    assert await async_setup_component(hass, "sensor", sens_cfg)
    assert 1 not in numato_fixture.devices[0].ports
