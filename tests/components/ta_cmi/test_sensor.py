"""Test the Technische Alternative C.M.I. sensor."""
from typing import Any
from unittest.mock import patch

from ta_cmi import InvalidCredentialsError

from homeassistant.components.sensor import DEVICE_CLASS_GAS, DEVICE_CLASS_TEMPERATURE
from homeassistant.components.ta_cmi.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import sleep_mock

from tests.common import MockConfigEntry

DUMMY_DEVICE_API_DATA: dict[str, Any] = {
    "Header": {"Version": 5, "Device": "87", "Timestamp": 1630764000},
    "Data": {
        "Inputs": [
            {"Number": 1, "AD": "A", "Value": {"Value": 92.2, "Unit": "1"}},
            {"Number": 2, "AD": "A", "Value": {"Value": 92.3, "Unit": "1"}},
            {"Number": 3, "AD": "A", "Value": {"Value": 1, "Unit": "44"}},
        ],
        "Outputs": [
            {"Number": 1, "AD": "D", "Value": {"Value": 1, "Unit": "43"}},
            {"Number": 2, "AD": "D", "Value": {"Value": 0, "Unit": "43"}},
            {"Number": 3, "AD": "D", "Value": {"Value": 1, "Unit": "44"}},
            {"Number": 4, "AD": "D", "Value": {"Value": 0, "Unit": "44"}},
            {"Number": 5, "AD": "D", "Value": {"Value": 0, "Unit": "1"}},
        ],
    },
    "Status": "OK",
    "Status code": 0,
}

ENTRY_DATA: dict[str, Any] = {
    "host": "http://192.168.2.101",
    "username": "admin",
    "password": "admin",
    "devices": [
        {
            "id": "2",
            "fetchmode": "all",
            "channels": [
                {
                    "type": "input",
                    "id": 1,
                    "name": "Input 1",
                    "device_class": DEVICE_CLASS_TEMPERATURE,
                },
                {
                    "type": "output",
                    "id": 1,
                    "name": "Output 1",
                    "device_class": DEVICE_CLASS_GAS,
                },
            ],
        },
        {
            "id": "5",
            "fetchmode": "defined",
            "channels": [],
        },
    ],
}


async def test_sensors(hass: HomeAssistant) -> None:
    """Test the creation and values of the sensors."""
    with patch("ta_cmi.baseApi.BaseAPI._makeRequestNoJson", return_value="2;",), patch(
        "ta_cmi.baseApi.BaseAPI._makeRequest", return_value=DUMMY_DEVICE_API_DATA
    ), patch("homeassistant.components.ta_cmi.const.DEVICE_DELAY", 1), patch(
        "asyncio.sleep", wraps=sleep_mock
    ):

        conf_entry: MockConfigEntry = MockConfigEntry(
            domain=DOMAIN, title="NINA", data=ENTRY_DATA
        )

        entity_registry: er = er.async_get(hass)
        conf_entry.add_to_hass(hass)

        await hass.config_entries.async_setup(conf_entry.entry_id)
        await hass.async_block_till_done()

        assert conf_entry.state == ConfigEntryState.LOADED

        state_i1 = hass.states.get("sensor.input_1")
        entry_i1 = entity_registry.async_get("sensor.input_1")

        assert state_i1.state == "92.2"
        assert state_i1.attributes.get("friendly_name") == "Input 1"
        assert state_i1.attributes.get("device_class") == DEVICE_CLASS_TEMPERATURE

        assert entry_i1.unique_id == "ta-cmi-2-Input1"

        state_i2 = hass.states.get("sensor.node_2_input_2")
        entry_i2 = entity_registry.async_get("sensor.node_2_input_2")

        assert state_i2.state == "92.3"
        assert state_i2.attributes.get("friendly_name") == "Node: 2 - Input 2"
        assert state_i2.attributes.get("device_class") == DEVICE_CLASS_TEMPERATURE

        assert entry_i2.unique_id == "ta-cmi-2-Input2"

        state_i3 = hass.states.get("binary_sensor.node_2_input_3")
        entry_i3 = entity_registry.async_get("binary_sensor.node_2_input_3")

        assert state_i3.state == STATE_ON
        assert state_i3.attributes.get("friendly_name") == "Node: 2 - Input 3"
        assert state_i3.attributes.get("device_class") == ""

        assert entry_i3.unique_id == "ta-cmi-2-Input3"

        state_o1 = hass.states.get("binary_sensor.output_1")
        entry_o1 = entity_registry.async_get("binary_sensor.output_1")

        assert state_o1.state == STATE_ON
        assert state_o1.attributes.get("friendly_name") == "Output 1"
        assert state_o1.attributes.get("device_class") == DEVICE_CLASS_GAS

        assert entry_o1.unique_id == "ta-cmi-2-Output1"

        state_o2 = hass.states.get("binary_sensor.node_2_output_2")
        entry_o2 = entity_registry.async_get("binary_sensor.node_2_output_2")

        assert state_o2.state == STATE_OFF
        assert state_o2.attributes.get("friendly_name") == "Node: 2 - Output 2"
        assert state_o2.attributes.get("device_class") == ""

        assert entry_o2.unique_id == "ta-cmi-2-Output2"

        state_o3 = hass.states.get("binary_sensor.node_2_output_3")
        entry_o3 = entity_registry.async_get("binary_sensor.node_2_output_3")

        assert state_o3.state == STATE_ON
        assert state_o3.attributes.get("friendly_name") == "Node: 2 - Output 3"
        assert state_o3.attributes.get("device_class") == ""

        assert entry_o3.unique_id == "ta-cmi-2-Output3"

        state_o4 = hass.states.get("binary_sensor.node_2_output_4")
        entry_o4 = entity_registry.async_get("binary_sensor.node_2_output_4")

        assert state_o4.state == STATE_OFF
        assert state_o4.attributes.get("friendly_name") == "Node: 2 - Output 4"
        assert state_o4.attributes.get("device_class") == ""

        assert entry_o4.unique_id == "ta-cmi-2-Output4"

        state_o5 = hass.states.get("sensor.node_2_output_5")
        entry_o5 = entity_registry.async_get("sensor.node_2_output_5")

        assert state_o5.state == "0"
        assert state_o5.attributes.get("friendly_name") == "Node: 2 - Output 5"
        assert state_o5.attributes.get("device_class") == DEVICE_CLASS_TEMPERATURE

        assert entry_o5.unique_id == "ta-cmi-2-Output5"


async def test_sensors_invalid_credentials(hass: HomeAssistant) -> None:
    """Test the creation and values of the sensors with invalid credentials."""
    with patch(
        "ta_cmi.baseApi.BaseAPI._makeRequestNoJson",
        side_effect=InvalidCredentialsError("Invalid API key"),
    ), patch("asyncio.sleep", wraps=sleep_mock):

        conf_entry: MockConfigEntry = MockConfigEntry(
            domain=DOMAIN, title="NINA", data=ENTRY_DATA
        )

        conf_entry.add_to_hass(hass)

        await hass.config_entries.async_setup(conf_entry.entry_id)
        await hass.async_block_till_done()

        assert conf_entry.state == ConfigEntryState.SETUP_RETRY
