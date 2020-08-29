"""Test the Tado config flow."""
import os

import serial.tools.list_ports

from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.rfxtrx import DOMAIN, config_flow
from homeassistant.helpers.device_registry import (
    async_entries_for_config_entry,
    async_get_registry,
)

from tests.async_mock import MagicMock, patch, sentinel
from tests.common import MockConfigEntry


def serial_connect(self):
    """Mock a serial connection."""
    self.serial = True


def serial_connect_fail(self):
    """Mock a failed serial connection."""
    self.serial = None


def com_port():
    """Mock of a serial port."""
    port = serial.tools.list_ports_common.ListPortInfo()
    port.serial_number = "1234"
    port.manufacturer = "Virtual serial port"
    port.device = "/dev/ttyUSB1234"
    port.description = "Some serial port"

    return port


@patch(
    "homeassistant.components.rfxtrx.rfxtrxmod.PyNetworkTransport.connect",
    return_value=None,
)
async def test_setup_network(connect_mock, hass):
    """Test we can setup network."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"type": "Network"},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "setup_network"
    assert result["errors"] == {}

    with patch("homeassistant.components.rfxtrx.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "10.10.0.1", "port": 1234}
        )

    assert result["type"] == "create_entry"
    assert result["title"] == "RFXTRX"
    assert result["data"] == {
        "host": "10.10.0.1",
        "port": 1234,
        "device": None,
        "automatic_add": False,
        "debug": False,
        "devices": {},
    }


@patch("serial.tools.list_ports.comports", return_value=[com_port()])
@patch(
    "homeassistant.components.rfxtrx.rfxtrxmod.PySerialTransport.connect",
    serial_connect,
)
@patch(
    "homeassistant.components.rfxtrx.rfxtrxmod.PySerialTransport.close",
    return_value=None,
)
async def test_setup_serial(com_mock, connect_mock, hass):
    """Test we can setup serial."""
    port = com_port()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"type": "Serial"},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "setup_serial"
    assert result["errors"] == {}

    with patch("homeassistant.components.rfxtrx.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"device": port.device}
        )

    assert result["type"] == "create_entry"
    assert result["title"] == "RFXTRX"
    assert result["data"] == {
        "host": None,
        "port": None,
        "device": port.device,
        "automatic_add": False,
        "debug": False,
        "devices": {},
    }


@patch("serial.tools.list_ports.comports", return_value=[com_port()])
@patch(
    "homeassistant.components.rfxtrx.rfxtrxmod.PySerialTransport.connect",
    serial_connect,
)
@patch(
    "homeassistant.components.rfxtrx.rfxtrxmod.PySerialTransport.close",
    return_value=None,
)
async def test_setup_serial_manual(com_mock, connect_mock, hass):
    """Test we can setup serial with manual entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"type": "Serial"},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "setup_serial"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"device": "Enter Manually"}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "setup_serial_manual_path"
    assert result["errors"] == {}

    with patch("homeassistant.components.rfxtrx.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"device": "/dev/ttyUSB0"}
        )

    assert result["type"] == "create_entry"
    assert result["title"] == "RFXTRX"
    assert result["data"] == {
        "host": None,
        "port": None,
        "device": "/dev/ttyUSB0",
        "automatic_add": False,
        "debug": False,
        "devices": {},
    }


@patch(
    "homeassistant.components.rfxtrx.rfxtrxmod.PyNetworkTransport.connect",
    side_effect=OSError,
)
async def test_setup_network_fail(connect_mock, hass):
    """Test we can setup network."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"type": "Network"},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "setup_network"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": "10.10.0.1", "port": 1234}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "setup_network"
    assert result["errors"] == {"base": "cannot_connect"}


@patch("serial.tools.list_ports.comports", return_value=[com_port()])
@patch(
    "homeassistant.components.rfxtrx.rfxtrxmod.PySerialTransport.connect",
    side_effect=serial.serialutil.SerialException,
)
async def test_setup_serial_fail(com_mock, connect_mock, hass):
    """Test setup serial failed connection."""
    port = com_port()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"type": "Serial"},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "setup_serial"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"device": port.device}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "setup_serial"
    assert result["errors"] == {"base": "cannot_connect"}


@patch("serial.tools.list_ports.comports", return_value=[com_port()])
@patch(
    "homeassistant.components.rfxtrx.rfxtrxmod.PySerialTransport.connect",
    serial_connect_fail,
)
async def test_setup_serial_manual_fail(com_mock, hass):
    """Test setup serial failed connection."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"type": "Serial"},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "setup_serial"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"device": "Enter Manually"}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "setup_serial_manual_path"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"device": "/dev/ttyUSB0"}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "setup_serial_manual_path"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_import(hass):
    """Test we can import."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={"host": None, "port": None, "device": "/dev/tty123", "debug": False},
    )

    assert result["type"] == "create_entry"
    assert result["title"] == "RFXTRX"
    assert result["data"] == {
        "host": None,
        "port": None,
        "device": "/dev/tty123",
        "debug": False,
    }


async def test_import_update(hass):
    """Test we can import."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"host": None, "port": None, "device": "/dev/tty123", "debug": False},
        unique_id=DOMAIN,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={"host": None, "port": None, "device": "/dev/tty123", "debug": True},
    )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_options_global(hass):
    """Test if we can set global options."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": None,
            "port": None,
            "device": "/dev/tty123",
            "debug": False,
            "automatic_add": False,
            "devices": {},
        },
        unique_id=DOMAIN,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == "form"
    assert result["step_id"] == "prompt_options"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"debug": True, "automatic_add": True}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY

    await hass.async_block_till_done()

    assert entry.data["debug"]
    assert entry.data["automatic_add"]


async def test_options_add_device(hass):
    """Test we can add a device."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": None,
            "port": None,
            "device": "/dev/tty123",
            "debug": False,
            "automatic_add": False,
            "devices": {},
        },
        unique_id=DOMAIN,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == "form"
    assert result["step_id"] == "prompt_options"

    # Try with invalid event code
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"debug": True, "automatic_add": True, "event_code": "1234"},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "prompt_options"
    assert result["errors"]
    assert result["errors"]["event_code"] == "invalid_event_code"

    # Try with valid event code
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "debug": True,
            "automatic_add": True,
            "event_code": "0b1100cd0213c7f230010f71",
        },
    )

    assert result["type"] == "form"
    assert result["step_id"] == "set_device_options"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"fire_event": True, "signal_repetitions": 5}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY

    await hass.async_block_till_done()

    assert entry.data["debug"]
    assert entry.data["automatic_add"]

    assert entry.data["devices"]["0b1100cd0213c7f230010f71"]
    assert entry.data["devices"]["0b1100cd0213c7f230010f71"]["fire_event"]
    assert entry.data["devices"]["0b1100cd0213c7f230010f71"]["signal_repetitions"] == 5
    assert "delay_off" not in entry.data["devices"]["0b1100cd0213c7f230010f71"]

    state = hass.states.get("binary_sensor.ac_213c7f2_48")
    assert state
    assert state.state == "off"
    assert state.attributes.get("friendly_name") == "AC 213c7f2:48"


async def test_options_add_remove_device(hass):
    """Test we can add a device."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": None,
            "port": None,
            "device": "/dev/tty123",
            "debug": False,
            "automatic_add": False,
            "devices": {},
        },
        unique_id=DOMAIN,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == "form"
    assert result["step_id"] == "prompt_options"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "debug": True,
            "automatic_add": True,
            "event_code": "0b1100cd0213c7f230010f71",
        },
    )

    assert result["type"] == "form"
    assert result["step_id"] == "set_device_options"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"fire_event": True, "signal_repetitions": 5, "off_delay": "4"},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY

    await hass.async_block_till_done()

    assert entry.data["debug"]
    assert entry.data["automatic_add"]

    assert entry.data["devices"]["0b1100cd0213c7f230010f71"]
    assert entry.data["devices"]["0b1100cd0213c7f230010f71"]["fire_event"]
    assert entry.data["devices"]["0b1100cd0213c7f230010f71"]["signal_repetitions"] == 5
    assert entry.data["devices"]["0b1100cd0213c7f230010f71"]["off_delay"] == 4

    state = hass.states.get("binary_sensor.ac_213c7f2_48")
    assert state
    assert state.state == "off"
    assert state.attributes.get("friendly_name") == "AC 213c7f2:48"

    device_registry = await async_get_registry(hass)
    device_entries = async_entries_for_config_entry(device_registry, entry.entry_id)

    assert device_entries[0].id

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == "form"
    assert result["step_id"] == "prompt_options"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "debug": False,
            "automatic_add": False,
            "remove_device": device_entries[0].id,
        },
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY

    await hass.async_block_till_done()

    assert not entry.data["debug"]
    assert not entry.data["automatic_add"]

    assert "0b1100cd0213c7f230010f71" not in entry.data["devices"]

    state = hass.states.get("binary_sensor.ac_213c7f2_48")
    assert not state


async def test_options_add_and_configure_device(hass):
    """Test we can add a device."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": None,
            "port": None,
            "device": "/dev/tty123",
            "debug": False,
            "automatic_add": False,
            "devices": {},
        },
        unique_id=DOMAIN,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == "form"
    assert result["step_id"] == "prompt_options"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "debug": True,
            "automatic_add": True,
            "event_code": "0913000022670e013970",
        },
    )

    assert result["type"] == "form"
    assert result["step_id"] == "set_device_options"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "fire_event": False,
            "signal_repetitions": 5,
            "data_bits": 4,
            "off_delay": "abcdef",
            "command_on": "xyz",
            "command_off": "xyz",
        },
    )

    assert result["type"] == "form"
    assert result["step_id"] == "set_device_options"
    assert result["errors"]
    assert result["errors"]["off_delay"] == "invalid_input_off_delay"
    assert result["errors"]["command_on"] == "invalid_input_2262_on"
    assert result["errors"]["command_off"] == "invalid_input_2262_off"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "fire_event": False,
            "signal_repetitions": 5,
            "data_bits": 4,
            "command_on": "0xE",
            "command_off": "0x7",
            "off_delay": "9",
        },
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY

    await hass.async_block_till_done()

    assert entry.data["debug"]
    assert entry.data["automatic_add"]

    assert entry.data["devices"]["0913000022670e013970"]
    assert not entry.data["devices"]["0913000022670e013970"]["fire_event"]
    assert entry.data["devices"]["0913000022670e013970"]["signal_repetitions"] == 5
    assert entry.data["devices"]["0913000022670e013970"]["off_delay"] == 9

    state = hass.states.get("binary_sensor.pt2262_22670e")
    assert state
    assert state.state == "off"
    assert state.attributes.get("friendly_name") == "PT2262 22670e"

    device_registry = await async_get_registry(hass)
    device_entries = async_entries_for_config_entry(device_registry, entry.entry_id)

    assert device_entries[0].id

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == "form"
    assert result["step_id"] == "prompt_options"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "debug": False,
            "automatic_add": False,
            "device": device_entries[0].id,
        },
    )

    assert result["type"] == "form"
    assert result["step_id"] == "set_device_options"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "fire_event": True,
            "signal_repetitions": 5,
            "data_bits": 4,
            "command_on": "0xE",
            "command_off": "0x7",
        },
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY

    await hass.async_block_till_done()

    assert entry.data["devices"]["0913000022670e013970"]
    assert entry.data["devices"]["0913000022670e013970"]["fire_event"]
    assert entry.data["devices"]["0913000022670e013970"]["signal_repetitions"] == 5
    assert "delay_off" not in entry.data["devices"]["0913000022670e013970"]


def test_get_serial_by_id_no_dir():
    """Test serial by id conversion if there's no /dev/serial/by-id."""
    p1 = patch("os.path.isdir", MagicMock(return_value=False))
    p2 = patch("os.scandir")
    with p1 as is_dir_mock, p2 as scan_mock:
        res = config_flow.get_serial_by_id(sentinel.path)
        assert res is sentinel.path
        assert is_dir_mock.call_count == 1
        assert scan_mock.call_count == 0


def test_get_serial_by_id():
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
