"""Tests for the numato integration."""
from copy import copy, deepcopy

from numato_gpio import NumatoGpioError
import pytest

import homeassistant.components.numato as numato
from homeassistant.helpers import discovery
from homeassistant.setup import async_setup_component

from . import numato_mock

from tests.components.switch.common import async_turn_off, async_turn_on

NUMATO_CFG = {
    "numato": {
        "discover": ["/ttyACM0", "/ttyACM1"],
        "devices": [
            {
                "id": 0,
                "binary_sensors": {
                    "invert_logic": False,
                    "ports": {
                        "2": "numato_binary_sensor_mock_port2",
                        "3": "numato_binary_sensor_mock_port3",
                        "4": "numato_binary_sensor_mock_port4",
                    },
                },
                "sensors": {
                    "ports": {
                        "1": {
                            "name": "numato_adc_mock_port1",
                            "source_range": [100, 1023],
                            "destination_range": [0, 10],
                            "unit": "mocks",
                        }
                    },
                },
                "switches": {
                    "invert_logic": False,
                    "ports": {
                        "5": "numato_switch_mock_port5",
                        "6": "numato_switch_mock_port6",
                    },
                },
            }
        ],
    }
}


def mockup_raise(*args, **kwargs):
    """Mockup to replace regular functions for error injection."""
    raise NumatoGpioError("Error mockup")


def mockup_return(*args, **kwargs):
    """Mockup to replace regular functions for error injection."""
    return False


@pytest.fixture
def config():
    """Provide a copy of the numato domain's test configuration.

    This helps to quickly change certain aspects of the configuration scoped
    to each individual test.
    """
    return deepcopy(NUMATO_CFG)


@pytest.fixture
def numato_fixture():
    """Inject the numato mockup into numato homeassistant module."""
    module_mock = copy(numato_mock.NumatoModuleMock)
    numato.__dict__["gpio"] = module_mock
    yield module_mock
    module_mock.cleanup()


@pytest.mark.asyncio
async def test_setup_no_devices(hass, numato_fixture, monkeypatch):
    """Test handling of an 'empty' discovery.

    Platform setups are expected to return after handling errors locally
    without raising.
    """
    monkeypatch.setattr(numato_fixture, "discover", mockup_return)
    assert await async_setup_component(hass, "numato", NUMATO_CFG)
    assert len(numato_fixture.devices) == 0


@pytest.mark.asyncio
async def test_fail_setup_raising_discovery(hass, numato_fixture, caplog, monkeypatch):
    """Test handling of an exception during discovery.

    Setup shall return False.
    """
    monkeypatch.setattr(numato_fixture, "discover", mockup_raise)
    assert not await async_setup_component(hass, "numato", NUMATO_CFG)
    await hass.async_block_till_done()


@pytest.mark.asyncio
async def test_regular_hass_operations(hass, numato_fixture):
    """Test regular operations from within Home Assistant."""
    assert await async_setup_component(hass, "numato", NUMATO_CFG)
    await hass.async_block_till_done()  # wait until services are registered
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


@pytest.mark.asyncio
async def test_failing_hass_operations(hass, numato_fixture, monkeypatch):
    """Test regular operations from within Home Assistant."""
    assert await async_setup_component(hass, "numato", NUMATO_CFG)

    await hass.async_block_till_done()  # wait until services are registered
    monkeypatch.setattr(numato_fixture.devices[0], "write", mockup_raise)
    await async_turn_on(hass, "switch.numato_switch_mock_port5")
    assert not numato_fixture.devices[0].values[5]
    await async_turn_on(hass, "switch.numato_switch_mock_port6")
    assert not numato_fixture.devices[0].values[6]
    await async_turn_off(hass, "switch.numato_switch_mock_port5")
    assert not numato_fixture.devices[0].values[5]
    await async_turn_off(hass, "switch.numato_switch_mock_port6")
    assert not numato_fixture.devices[0].values[6]


@pytest.mark.asyncio
async def test_hass_numato_api(hass, numato_fixture):
    """Test regular device access."""
    assert await async_setup_component(hass, "numato", NUMATO_CFG)
    api = hass.data["numato"]["api"]
    # regular operations
    api.read_adc_input(0, 1)
    api.read_input(0, 2)
    api.write_output(0, 2, 1)

    def gen_callback(expected_port, expected_value):
        def cb_mockup(port, value):
            assert port == expected_port
            assert value == expected_value

        return cb_mockup

    api.edge_detect(0, 2, gen_callback(2, 1))
    numato_fixture.devices[0].mockup_inject_notification(2, 1)
    api.edge_detect(0, 2, gen_callback(2, 0))
    numato_fixture.devices[0].mockup_inject_notification(2, 0)


@pytest.mark.asyncio
async def test_hass_numato_api_irregular_unhandled(hass, numato_fixture):
    """Test irregular, unhandled operations.

    Establishes that these don't throw from numato-gpio or are handled in the
    numato component's API.
    """
    assert await async_setup_component(hass, "numato", NUMATO_CFG)
    api = hass.data["numato"]["api"]
    api.read_adc_input(0, 5)  # adc_read from output
    api.read_input(0, 6)  # read from output
    api.write_output(0, 2, 1)  # write to input


@pytest.mark.asyncio
async def test_hass_numato_api_errors(hass, numato_fixture, monkeypatch):
    """Test whether Home Assistant numato API (re-)raises errors."""
    numato_fixture.discover()
    monkeypatch.setattr(numato_fixture.devices[0], "setup", mockup_raise)
    monkeypatch.setattr(numato_fixture.devices[0], "adc_read", mockup_raise)
    monkeypatch.setattr(numato_fixture.devices[0], "read", mockup_raise)
    monkeypatch.setattr(numato_fixture.devices[0], "write", mockup_raise)
    api = numato.NumatoAPI()
    with pytest.raises(NumatoGpioError):
        api.setup_input(0, 5)
        api.read_adc_input(0, 1)
        api.read_input(0, 2)
        api.write_output(0, 2, 1)


@pytest.mark.asyncio
async def test_invalid_port_number(hass, numato_fixture, config):
    """Test validation of ADC port number type."""
    sensorports_cfg = config["numato"]["devices"][0]["sensors"]["ports"]
    port1_config = sensorports_cfg["1"]
    sensorports_cfg["one"] = port1_config
    del sensorports_cfg["1"]
    assert not await async_setup_component(hass, "numato", config)
    await hass.async_block_till_done()
    assert not numato_fixture.devices


@pytest.mark.asyncio
async def test_too_low_adc_port_number(hass, numato_fixture, config):
    """Test handling of failing component setup.

    Tries setting up an ADC on a port below (0) the allowed range.
    """

    sensorports_cfg = config["numato"]["devices"][0]["sensors"]["ports"]
    sensorports_cfg.update({0: {"name": "toolow"}})
    assert not await async_setup_component(hass, "numato", config)
    assert not numato_fixture.devices


@pytest.mark.asyncio
async def test_too_high_adc_port_number(hass, numato_fixture, config):
    """Test handling of failing component setup.

    Tries setting up an ADC on a port above (8) the allowed range.
    """
    sensorports_cfg = config["numato"]["devices"][0]["sensors"]["ports"]
    sensorports_cfg.update({8: {"name": "toohigh"}})
    assert not await async_setup_component(hass, "numato", config)
    assert not numato_fixture.devices


@pytest.mark.asyncio
async def test_invalid_adc_range_value_type(hass, numato_fixture, config):
    """Test validation of ADC range config's types.

    Replaces the source range beginning by a string.
    """
    sensorports_cfg = config["numato"]["devices"][0]["sensors"]["ports"]
    sensorports_cfg["1"]["source_range"][0] = "zero"
    assert not await async_setup_component(hass, "numato", config)
    assert not numato_fixture.devices


@pytest.mark.asyncio
async def test_invalid_adc_source_range_length(hass, numato_fixture, config):
    """Test validation of ADC range config's length.

    Adds an element to the source range.
    """
    sensorports_cfg = config["numato"]["devices"][0]["sensors"]["ports"]
    sensorports_cfg["1"]["source_range"].append(42)
    assert not await async_setup_component(hass, "numato", config)
    assert not numato_fixture.devices


@pytest.mark.asyncio
async def test_invalid_adc_source_range_order(hass, numato_fixture, config):
    """Test validation of ADC range config's order.

    Sets the source range to a decreasing [2, 1].
    """
    sensorports_cfg = config["numato"]["devices"][0]["sensors"]["ports"]
    sensorports_cfg["1"]["source_range"] = [2, 1]
    assert not await async_setup_component(hass, "numato", config)
    assert not numato_fixture.devices


@pytest.mark.asyncio
async def test_invalid_adc_destination_range_value_type(hass, numato_fixture, config):
    """Test validation of ADC range .

    Replaces the destination range beginning by a string.
    """
    sensorports_cfg = config["numato"]["devices"][0]["sensors"]["ports"]
    sensorports_cfg["1"]["destination_range"][0] = "zero"
    assert not await async_setup_component(hass, "numato", config)
    assert not numato_fixture.devices


@pytest.mark.asyncio
async def test_invalid_adc_destination_range_length(hass, numato_fixture, config):
    """Test validation of ADC range config's length.

    Adds an element to the destination range.
    """
    sensorports_cfg = config["numato"]["devices"][0]["sensors"]["ports"]
    sensorports_cfg["1"]["destination_range"].append(42)
    assert not await async_setup_component(hass, "numato", config)
    assert not numato_fixture.devices


@pytest.mark.asyncio
async def test_invalid_adc_destination_range_order(hass, numato_fixture, config):
    """Test validation of ADC range config's order.

    Sets the destination range to a decreasing [2, 1].
    """
    sensorports_cfg = config["numato"]["devices"][0]["sensors"]["ports"]
    sensorports_cfg["1"]["destination_range"] = [2, 1]
    assert not await async_setup_component(hass, "numato", config)
    assert not numato_fixture.devices


@pytest.mark.asyncio
async def test_platform_setup_without_discovery_info(hass, config):
    """Test handling of empty discovery_info."""
    discovery.load_platform(hass, "binary_sensor", "numato", None, config)
    discovery.load_platform(hass, "sensor", "numato", None, config)
    discovery.load_platform(hass, "switch", "numato", None, config)
    await hass.async_block_till_done()
