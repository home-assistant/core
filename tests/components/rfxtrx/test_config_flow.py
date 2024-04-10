"""Test the Rfxtrx config flow."""

import os
from unittest.mock import MagicMock, patch, sentinel

from RFXtrx import RFXtrxTransportError
import serial.tools.list_ports

from homeassistant import config_entries
from homeassistant.components.rfxtrx import DOMAIN, config_flow
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry

SOME_PROTOCOLS = ["ac", "arc"]


def com_port():
    """Mock of a serial port."""
    port = serial.tools.list_ports_common.ListPortInfo("/dev/ttyUSB1234")
    port.serial_number = "1234"
    port.manufacturer = "Virtual serial port"
    port.device = "/dev/ttyUSB1234"
    port.description = "Some serial port"

    return port


async def start_options_flow(hass, entry):
    """Start the options flow with the entry under test."""
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return await hass.config_entries.options.async_init(entry.entry_id)


async def test_setup_network(transport_mock, hass: HomeAssistant) -> None:
    """Test we can setup network."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"type": "Network"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "setup_network"
    assert result["errors"] == {}

    with patch("homeassistant.components.rfxtrx.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "10.10.0.1", "port": 1234}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "RFXTRX"
    assert result["data"] == {
        "host": "10.10.0.1",
        "port": 1234,
        "device": None,
        "automatic_add": False,
        "devices": {},
    }


@patch("serial.tools.list_ports.comports", return_value=[com_port()])
async def test_setup_serial(com_mock, transport_mock, hass: HomeAssistant) -> None:
    """Test we can setup serial."""
    port = com_port()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"type": "Serial"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "setup_serial"
    assert result["errors"] == {}

    with patch("homeassistant.components.rfxtrx.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"device": port.device}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "RFXTRX"
    assert result["data"] == {
        "host": None,
        "port": None,
        "device": port.device,
        "automatic_add": False,
        "devices": {},
    }


@patch("serial.tools.list_ports.comports", return_value=[com_port()])
async def test_setup_serial_manual(
    com_mock, transport_mock, hass: HomeAssistant
) -> None:
    """Test we can setup serial with manual entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"type": "Serial"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "setup_serial"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"device": "Enter Manually"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "setup_serial_manual_path"
    assert result["errors"] == {}

    with patch("homeassistant.components.rfxtrx.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"device": "/dev/ttyUSB0"}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "RFXTRX"
    assert result["data"] == {
        "host": None,
        "port": None,
        "device": "/dev/ttyUSB0",
        "automatic_add": False,
        "devices": {},
    }


async def test_setup_network_fail(transport_mock, hass: HomeAssistant) -> None:
    """Test we can setup network."""
    transport_mock.return_value.connect.side_effect = RFXtrxTransportError
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"type": "Network"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "setup_network"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": "10.10.0.1", "port": 1234}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "setup_network"
    assert result["errors"] == {"base": "cannot_connect"}


@patch("serial.tools.list_ports.comports", return_value=[com_port()])
async def test_setup_serial_fail(com_mock, transport_mock, hass: HomeAssistant) -> None:
    """Test setup serial failed connection."""
    transport_mock.return_value.connect.side_effect = RFXtrxTransportError
    port = com_port()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"type": "Serial"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "setup_serial"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"device": port.device}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "setup_serial"
    assert result["errors"] == {"base": "cannot_connect"}


@patch("serial.tools.list_ports.comports", return_value=[com_port()])
async def test_setup_serial_manual_fail(
    com_mock, transport_mock, hass: HomeAssistant
) -> None:
    """Test setup serial failed connection."""
    transport_mock.return_value.connect.side_effect = RFXtrxTransportError
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"type": "Serial"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "setup_serial"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"device": "Enter Manually"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "setup_serial_manual_path"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"device": "/dev/ttyUSB0"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "setup_serial_manual_path"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_options_global(hass: HomeAssistant) -> None:
    """Test if we can set global options."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": None,
            "port": None,
            "device": "/dev/tty123",
            "automatic_add": False,
            "protocols": None,
            "devices": {},
        },
        unique_id=DOMAIN,
    )
    with patch("homeassistant.components.rfxtrx.async_setup_entry", return_value=True):
        result = await start_options_flow(hass, entry)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "prompt_options"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"automatic_add": True, "protocols": SOME_PROTOCOLS},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY

    await hass.async_block_till_done()

    assert entry.data["automatic_add"]

    assert not set(entry.data["protocols"]) ^ set(SOME_PROTOCOLS)


async def test_no_protocols(hass: HomeAssistant) -> None:
    """Test we set protocols to None if none are selected."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": None,
            "port": None,
            "device": "/dev/tty123",
            "automatic_add": True,
            "protocols": SOME_PROTOCOLS,
            "devices": {},
        },
        unique_id=DOMAIN,
    )
    with patch("homeassistant.components.rfxtrx.async_setup_entry", return_value=True):
        result = await start_options_flow(hass, entry)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "prompt_options"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"automatic_add": False, "protocols": []},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY

    await hass.async_block_till_done()

    assert not entry.data["automatic_add"]

    assert entry.data["protocols"] is None


async def test_options_add_device(hass: HomeAssistant) -> None:
    """Test we can add a device."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": None,
            "port": None,
            "device": "/dev/tty123",
            "automatic_add": False,
            "devices": {},
        },
        unique_id=DOMAIN,
    )
    result = await start_options_flow(hass, entry)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "prompt_options"

    # Try with invalid event code
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"automatic_add": True, "event_code": "1234"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "prompt_options"
    assert result["errors"]
    assert result["errors"]["event_code"] == "invalid_event_code"

    # Try with valid event code
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "automatic_add": True,
            "event_code": "0b1100cd0213c7f230010f71",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "set_device_options"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY

    await hass.async_block_till_done()

    assert entry.data["automatic_add"]

    assert entry.data["devices"]["0b1100cd0213c7f230010f71"]
    assert "delay_off" not in entry.data["devices"]["0b1100cd0213c7f230010f71"]

    state = hass.states.get("binary_sensor.ac_213c7f2_48")
    assert state
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get("friendly_name") == "AC 213c7f2:48"


async def test_options_add_duplicate_device(hass: HomeAssistant) -> None:
    """Test we can add a device."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": None,
            "port": None,
            "device": "/dev/tty123",
            "debug": False,
            "automatic_add": False,
            "devices": {"0b1100cd0213c7f230010f71": {}},
        },
        unique_id=DOMAIN,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "prompt_options"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "automatic_add": True,
            "event_code": "0b1100cd0213c7f230010f71",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "prompt_options"
    assert result["errors"]
    assert result["errors"]["event_code"] == "already_configured_device"


async def test_options_replace_sensor_device(hass: HomeAssistant) -> None:
    """Test we can replace a sensor device."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": None,
            "port": None,
            "device": "/dev/tty123",
            "automatic_add": False,
            "devices": {
                "0a520101f00400e22d0189": {"device_id": ["52", "1", "f0:04"]},
                "0a520105230400c3260279": {"device_id": ["52", "1", "23:04"]},
            },
        },
        unique_id=DOMAIN,
    )
    await start_options_flow(hass, entry)

    state = hass.states.get(
        "sensor.thgn122_123_thgn132_thgr122_228_238_268_f0_04_signal_strength"
    )
    assert state
    state = hass.states.get(
        "sensor.thgn122_123_thgn132_thgr122_228_238_268_f0_04_battery"
    )
    assert state
    state = hass.states.get(
        "sensor.thgn122_123_thgn132_thgr122_228_238_268_f0_04_humidity"
    )
    assert state
    state = hass.states.get(
        "sensor.thgn122_123_thgn132_thgr122_228_238_268_f0_04_humidity_status"
    )
    assert state
    state = hass.states.get(
        "sensor.thgn122_123_thgn132_thgr122_228_238_268_f0_04_temperature"
    )
    assert state
    state = hass.states.get(
        "sensor.thgn122_123_thgn132_thgr122_228_238_268_23_04_signal_strength"
    )
    assert state
    state = hass.states.get(
        "sensor.thgn122_123_thgn132_thgr122_228_238_268_23_04_battery"
    )
    assert state
    state = hass.states.get(
        "sensor.thgn122_123_thgn132_thgr122_228_238_268_23_04_humidity"
    )
    assert state
    state = hass.states.get(
        "sensor.thgn122_123_thgn132_thgr122_228_238_268_23_04_humidity_status"
    )
    assert state
    state = hass.states.get(
        "sensor.thgn122_123_thgn132_thgr122_228_238_268_23_04_temperature"
    )
    assert state

    device_registry = dr.async_get(hass)
    device_entries = dr.async_entries_for_config_entry(device_registry, entry.entry_id)

    old_device = next(
        (
            elem.id
            for elem in device_entries
            if next(iter(elem.identifiers))[1:] == ("52", "1", "f0:04")
        ),
        None,
    )
    new_device = next(
        (
            elem.id
            for elem in device_entries
            if next(iter(elem.identifiers))[1:] == ("52", "1", "23:04")
        ),
        None,
    )

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "prompt_options"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "automatic_add": False,
            "device": old_device,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "set_device_options"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "replace_device": new_device,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY

    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)

    entry = entity_registry.async_get(
        "sensor.thgn122_123_thgn132_thgr122_228_238_268_f0_04_signal_strength"
    )
    assert entry
    assert entry.device_id == new_device
    entry = entity_registry.async_get(
        "sensor.thgn122_123_thgn132_thgr122_228_238_268_f0_04_humidity"
    )
    assert entry
    assert entry.device_id == new_device
    entry = entity_registry.async_get(
        "sensor.thgn122_123_thgn132_thgr122_228_238_268_f0_04_humidity_status"
    )
    assert entry
    assert entry.device_id == new_device
    entry = entity_registry.async_get(
        "sensor.thgn122_123_thgn132_thgr122_228_238_268_f0_04_battery"
    )
    assert entry
    assert entry.device_id == new_device
    entry = entity_registry.async_get(
        "sensor.thgn122_123_thgn132_thgr122_228_238_268_f0_04_temperature"
    )
    assert entry
    assert entry.device_id == new_device

    state = hass.states.get(
        "sensor.thgn122_123_thgn132_thgr122_228_238_268_23_04_signal_strength"
    )
    assert not state
    state = hass.states.get(
        "sensor.thgn122_123_thgn132_thgr122_228_238_268_23_04_battery"
    )
    assert not state
    state = hass.states.get(
        "sensor.thgn122_123_thgn132_thgr122_228_238_268_23_04_humidity"
    )
    assert not state
    state = hass.states.get(
        "sensor.thgn122_123_thgn132_thgr122_228_238_268_23_04_humidity_status"
    )
    assert not state
    state = hass.states.get(
        "sensor.thgn122_123_thgn132_thgr122_228_238_268_23_04_temperature"
    )
    assert not state


async def test_options_replace_control_device(hass: HomeAssistant) -> None:
    """Test we can replace a control device."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": None,
            "port": None,
            "device": "/dev/tty123",
            "automatic_add": False,
            "devices": {
                "0b1100100118cdea02010f70": {
                    "device_id": ["11", "0", "118cdea:2"],
                },
                "0b1100101118cdea02010f70": {
                    "device_id": ["11", "0", "1118cdea:2"],
                },
            },
        },
        unique_id=DOMAIN,
    )
    await start_options_flow(hass, entry)

    state = hass.states.get("binary_sensor.ac_118cdea_2")
    assert state
    state = hass.states.get("sensor.ac_118cdea_2_signal_strength")
    assert state
    state = hass.states.get("switch.ac_118cdea_2")
    assert state
    state = hass.states.get("binary_sensor.ac_1118cdea_2")
    assert state
    state = hass.states.get("sensor.ac_1118cdea_2_signal_strength")
    assert state
    state = hass.states.get("switch.ac_1118cdea_2")
    assert state

    device_registry = dr.async_get(hass)
    device_entries = dr.async_entries_for_config_entry(device_registry, entry.entry_id)

    old_device = next(
        (
            elem.id
            for elem in device_entries
            if next(iter(elem.identifiers))[1:] == ("11", "0", "118cdea:2")
        ),
        None,
    )
    new_device = next(
        (
            elem.id
            for elem in device_entries
            if next(iter(elem.identifiers))[1:] == ("11", "0", "1118cdea:2")
        ),
        None,
    )

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "prompt_options"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "automatic_add": False,
            "device": old_device,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "set_device_options"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "replace_device": new_device,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY

    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)

    entry = entity_registry.async_get("binary_sensor.ac_118cdea_2")
    assert entry
    assert entry.device_id == new_device
    entry = entity_registry.async_get("sensor.ac_118cdea_2_signal_strength")
    assert entry
    assert entry.device_id == new_device
    entry = entity_registry.async_get("switch.ac_118cdea_2")
    assert entry
    assert entry.device_id == new_device

    state = hass.states.get("binary_sensor.ac_1118cdea_2")
    assert not state
    state = hass.states.get("sensor.ac_1118cdea_2_signal_strength")
    assert not state
    state = hass.states.get("switch.ac_1118cdea_2")
    assert not state


async def test_options_add_and_configure_device(hass: HomeAssistant) -> None:
    """Test we can add a device."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": None,
            "port": None,
            "device": "/dev/tty123",
            "automatic_add": False,
            "devices": {},
        },
        unique_id=DOMAIN,
    )
    result = await start_options_flow(hass, entry)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "prompt_options"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "automatic_add": True,
            "event_code": "0913000022670e013970",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "set_device_options"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "data_bits": 4,
            "off_delay": "abcdef",
            "command_on": "xyz",
            "command_off": "xyz",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "set_device_options"
    assert result["errors"]
    assert result["errors"]["off_delay"] == "invalid_input_off_delay"
    assert result["errors"]["command_on"] == "invalid_input_2262_on"
    assert result["errors"]["command_off"] == "invalid_input_2262_off"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "data_bits": 4,
            "command_on": "0xE",
            "command_off": "0x7",
            "off_delay": "9",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY

    await hass.async_block_till_done()

    assert entry.data["automatic_add"]

    assert entry.data["devices"]["0913000022670e013970"]
    assert entry.data["devices"]["0913000022670e013970"]["off_delay"] == 9

    state = hass.states.get("binary_sensor.pt2262_22670e")
    assert state
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get("friendly_name") == "PT2262 22670e"

    device_registry = dr.async_get(hass)
    device_entries = dr.async_entries_for_config_entry(device_registry, entry.entry_id)

    assert device_entries[0].id

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "prompt_options"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "automatic_add": False,
            "device": device_entries[0].id,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "set_device_options"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "data_bits": 4,
            "command_on": "0xE",
            "command_off": "0x7",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY

    await hass.async_block_till_done()

    assert entry.data["devices"]["0913000022670e013970"]
    assert "delay_off" not in entry.data["devices"]["0913000022670e013970"]


async def test_options_configure_rfy_cover_device(hass: HomeAssistant) -> None:
    """Test we can configure the venetion blind mode of an Rfy cover."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": None,
            "port": None,
            "device": "/dev/tty123",
            "automatic_add": False,
            "devices": {},
        },
        unique_id=DOMAIN,
    )
    result = await start_options_flow(hass, entry)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "prompt_options"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "automatic_add": True,
            "event_code": "0C1a0000010203010000000000",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "set_device_options"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "venetian_blind_mode": "EU",
        },
    )

    await hass.async_block_till_done()

    assert (
        entry.data["devices"]["0C1a0000010203010000000000"]["venetian_blind_mode"]
        == "EU"
    )
    assert isinstance(
        entry.data["devices"]["0C1a0000010203010000000000"]["device_id"], list
    )

    device_registry = dr.async_get(hass)
    device_entries = dr.async_entries_for_config_entry(device_registry, entry.entry_id)

    assert device_entries[0].id

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "prompt_options"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "automatic_add": False,
            "device": device_entries[0].id,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "set_device_options"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "venetian_blind_mode": "EU",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY

    await hass.async_block_till_done()

    assert (
        entry.data["devices"]["0C1a0000010203010000000000"]["venetian_blind_mode"]
        == "EU"
    )
    assert isinstance(
        entry.data["devices"]["0C1a0000010203010000000000"]["device_id"], list
    )


def test_get_serial_by_id_no_dir() -> None:
    """Test serial by id conversion if there's no /dev/serial/by-id."""
    p1 = patch("os.path.isdir", MagicMock(return_value=False))
    p2 = patch("os.scandir")
    with p1 as is_dir_mock, p2 as scan_mock:
        res = config_flow.get_serial_by_id(sentinel.path)
        assert res is sentinel.path
        assert is_dir_mock.call_count == 1
        assert scan_mock.call_count == 0


def test_get_serial_by_id() -> None:
    """Test serial by id conversion."""
    p1 = patch("os.path.isdir", MagicMock(return_value=True))
    p2 = patch("os.scandir")

    def _realpath(path):
        if path is sentinel.matched_link:
            return sentinel.path
        return sentinel.serial_link_path

    p3 = patch("os.path.realpath", side_effect=_realpath)
    with p1 as is_dir_mock, p2 as scan_mock, p3:
        res = config_flow.get_serial_by_id(sentinel.path)
        assert res is sentinel.path
        assert is_dir_mock.call_count == 1
        assert scan_mock.call_count == 1

        entry1 = MagicMock(spec_set=os.DirEntry)
        entry1.is_symlink.return_value = True
        entry1.path = sentinel.some_path

        entry2 = MagicMock(spec_set=os.DirEntry)
        entry2.is_symlink.return_value = False
        entry2.path = sentinel.other_path

        entry3 = MagicMock(spec_set=os.DirEntry)
        entry3.is_symlink.return_value = True
        entry3.path = sentinel.matched_link

        scan_mock.return_value = [entry1, entry2, entry3]
        res = config_flow.get_serial_by_id(sentinel.path)
        assert res is sentinel.matched_link
        assert is_dir_mock.call_count == 2
        assert scan_mock.call_count == 2
