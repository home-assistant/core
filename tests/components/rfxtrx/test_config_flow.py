"""Test the Rfxtrx config flow."""

import asyncio
from unittest.mock import patch

from RFXtrx import RFXtrxTransportError

from homeassistant import config_entries
from homeassistant.components.rfxtrx import DOMAIN
from homeassistant.components.usb import SerialDevice
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import ENTRY_VERSION

from tests.common import MockConfigEntry

SOME_PROTOCOLS = ["ac", "arc"]


def com_port() -> SerialDevice:
    """Mock of a serial port."""
    return SerialDevice(
        device="/dev/ttyUSB1234",
        serial_number="1234",
        manufacturer="Virtual serial port",
        description="Some serial port",
    )


async def start_options_flow(
    hass: HomeAssistant, entry: MockConfigEntry
) -> config_entries.ConfigFlowResult:
    """Start the options flow with the entry under test."""
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return await hass.config_entries.options.async_init(entry.entry_id)


async def start_add_device_flow(
    hass: HomeAssistant, entry: MockConfigEntry
) -> config_entries.ConfigFlowResult:
    """Start the add device subentry flow with the entry under test."""
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return await hass.config_entries.subentries.async_init(
        (entry.entry_id, "device"),
        context={"source": config_entries.SOURCE_USER},
    )


async def async_wait_for_reload(hass: HomeAssistant) -> None:
    """Wait for the entry's debounced reload to complete."""
    await hass.async_block_till_done()
    await asyncio.sleep(0)
    await hass.async_block_till_done()


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
    }


@patch(
    "homeassistant.components.rfxtrx.config_flow.usb.async_scan_serial_ports",
    return_value=[com_port()],
)
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
    }


@patch(
    "homeassistant.components.rfxtrx.config_flow.usb.async_scan_serial_ports",
    return_value=[com_port()],
)
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


@patch(
    "homeassistant.components.rfxtrx.config_flow.usb.async_scan_serial_ports",
    return_value=[com_port()],
)
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


@patch(
    "homeassistant.components.rfxtrx.config_flow.usb.async_scan_serial_ports",
    return_value=[com_port()],
)
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
        },
        unique_id=DOMAIN,
        version=ENTRY_VERSION,
    )
    with patch("homeassistant.components.rfxtrx.async_setup_entry", return_value=True):
        result = await start_options_flow(hass, entry)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

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
        },
        unique_id=DOMAIN,
        version=ENTRY_VERSION,
    )
    with patch("homeassistant.components.rfxtrx.async_setup_entry", return_value=True):
        result = await start_options_flow(hass, entry)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

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
        },
        unique_id=DOMAIN,
        version=ENTRY_VERSION,
    )
    result = await start_add_device_flow(hass, entry)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # Try with invalid event code
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={"event_code": "1234"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"]
    assert result["errors"]["event_code"] == "invalid_event_code"

    # Try with valid event code
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={"event_code": "0b1100cd0213c7f230010f71"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "device_options"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY

    await async_wait_for_reload(hass)

    subentry = next(iter(entry.subentries.values()))
    assert subentry.data["event_code"] == "0b1100cd0213c7f230010f71"
    assert "off_delay" not in subentry.data

    state = hass.states.get("binary_sensor.ac_213c7f2_48")
    assert state
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get("friendly_name") == "AC 213c7f2:48"


async def test_options_replace_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    rfxtrx,
) -> None:
    """Test pointing a configured device at different hardware.

    The device, its entities, and their identity (unique_id, entity_id,
    area/name customizations) are preserved across the radio address change
    since they are keyed by the subentry, not the RF address.
    """

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": None,
            "port": None,
            "device": "/dev/tty123",
            "automatic_add": False,
        },
        unique_id=DOMAIN,
        version=ENTRY_VERSION,
    )
    result = await start_add_device_flow(hass, entry)

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={"event_code": "0b1100cd0213c7f230010f71"},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY

    await async_wait_for_reload(hass)

    subentry = next(iter(entry.subentries.values()))
    device_entry = dr.async_entries_for_config_entry(device_registry, entry.entry_id)[0]
    entity_id = entity_registry.async_get_entity_id(
        "binary_sensor", DOMAIN, subentry.subentry_id
    )
    assert entity_id

    state = hass.states.get(entity_id)
    assert state
    assert state.attributes.get("friendly_name") == "AC 213c7f2:48"

    device_registry.async_update_device(device_entry.id, name_by_user="My custom name")

    # Point the same configured device at a different physical device
    result = await entry.start_subentry_reconfigure_flow(hass, subentry.subentry_id)
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={"event_code": "0b1100100118cdea02010f70"},
    )
    assert result["step_id"] == "device_options"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    await async_wait_for_reload(hass)

    subentry = entry.subentries[subentry.subentry_id]
    assert subentry.data["event_code"] == "0b1100100118cdea02010f70"

    # Same device, same entity, same customization - only the underlying
    # radio address changed.
    device_entry = device_registry.async_get(device_entry.id)
    assert device_entry
    assert device_entry.name_by_user == "My custom name"
    assert device_entry.name == "AC 118cdea:2"

    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry
    assert entity_entry.unique_id == subentry.subentry_id

    # The old radio address no longer applies to this entity
    state_before = hass.states.get(entity_id)
    assert state_before
    await rfxtrx.signal("0b1100cd0213c7f230010f71")
    state = hass.states.get(entity_id)
    assert state.last_updated == state_before.last_updated

    # The new radio address does
    await rfxtrx.signal("0b1100100118cdea02010f70")
    state = hass.states.get(entity_id)
    assert state.state == "on"


async def test_options_reconfigure_invalid_and_duplicate_event_code(
    hass: HomeAssistant,
) -> None:
    """Test entering an invalid or already configured event code on reconfigure."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": None,
            "port": None,
            "device": "/dev/tty123",
            "automatic_add": False,
        },
        unique_id=DOMAIN,
        version=ENTRY_VERSION,
    )

    # Add device A
    result = await start_add_device_flow(hass, entry)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={"event_code": "0b1100cd0213c7f230010f71"},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    subentry_a = next(iter(entry.subentries.values()))

    # Add device B, so there's another device to collide with
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "device"),
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={"event_code": "0b1100100118cdea02010f70"},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    # Reconfigure A with an invalid event code
    result = await entry.start_subentry_reconfigure_flow(hass, subentry_a.subentry_id)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={"event_code": "invalid"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["event_code"] == "invalid_event_code"

    # Reconfigure A, manually typing B's event code
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={"event_code": "0b1100100118cdea02010f70"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["event_code"] == "already_configured_device"


async def test_options_reconfigure_ignores_broken_subentries(
    hass: HomeAssistant,
) -> None:
    """Test add/reconfigure ignore non-device and invalid-event subentries."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": None,
            "port": None,
            "device": "/dev/tty123",
            "automatic_add": False,
        },
        subentries_data=(
            {
                "data": {},
                "subentry_type": "other",
                "title": "Not a device",
                "unique_id": None,
            },
            {
                "data": {"event_code": "invalid"},
                "subentry_type": "device",
                "title": "Broken device",
                "unique_id": None,
            },
        ),
        unique_id=DOMAIN,
        version=ENTRY_VERSION,
    )

    # Add a device - exercises _can_add_device skipping the "other" and
    # broken subentries instead of erroring on them.
    result = await start_add_device_flow(hass, entry)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={"event_code": "0b1100cd0213c7f230010f71"},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    device_subentry = next(
        s
        for s in entry.subentries.values()
        if s.data.get("event_code") == "0b1100cd0213c7f230010f71"
    )

    # Reconfiguring it exercises _get_replace_devices skipping the same
    # "other" and broken subentries.
    result = await entry.start_subentry_reconfigure_flow(
        hass, device_subentry.subentry_id
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"


async def test_options_replace_device_with_existing(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test picking another configured device to take over an address from.

    Device A keeps its identity (device, entities, customization); device
    B's event code is moved onto it and B's now-redundant subentry is
    removed.
    """

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": None,
            "port": None,
            "device": "/dev/tty123",
            "automatic_add": False,
        },
        unique_id=DOMAIN,
        version=ENTRY_VERSION,
    )

    # Add device A
    result = await start_add_device_flow(hass, entry)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={"event_code": "0b1100cd0213c7f230010f71"},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await async_wait_for_reload(hass)

    subentry_a = next(iter(entry.subentries.values()))
    device_a = dr.async_entries_for_config_entry(device_registry, entry.entry_id)[0]
    entity_id_a = entity_registry.async_get_entity_id(
        "binary_sensor", DOMAIN, subentry_a.subentry_id
    )
    assert entity_id_a
    device_registry.async_update_device(device_a.id, name_by_user="My custom name")

    # Add device B (same protocol/type as A)
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "device"),
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={"event_code": "0b1100100118cdea02010f70"},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await async_wait_for_reload(hass)

    subentry_b_id = next(
        s.subentry_id for s in entry.subentries.values() if s != subentry_a
    )

    # Reconfigure A, picking B as the device to take over
    result = await entry.start_subentry_reconfigure_flow(hass, subentry_a.subentry_id)
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={"replace_device": subentry_b_id},
    )
    assert result["step_id"] == "device_options"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    await async_wait_for_reload(hass)

    # A kept its identity and customization, but now has B's event code
    assert entry.subentries.keys() == {subentry_a.subentry_id}
    subentry_a = entry.subentries[subentry_a.subentry_id]
    assert subentry_a.data["event_code"] == "0b1100100118cdea02010f70"

    device_a = device_registry.async_get(device_a.id)
    assert device_a
    assert device_a.name_by_user == "My custom name"
    assert device_a.name == "AC 118cdea:2"

    entity_a = entity_registry.async_get(entity_id_a)
    assert entity_a
    assert entity_a.unique_id == subentry_a.subentry_id


async def test_options_replace_device_coalesces_reload(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test replacing a device only reloads the entry once.

    The replace flow both removes the source subentry and updates the
    target subentry, each of which notifies the entry's update listener;
    those should be coalesced into a single reload.
    """

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": None,
            "port": None,
            "device": "/dev/tty123",
            "automatic_add": False,
        },
        unique_id=DOMAIN,
        version=ENTRY_VERSION,
    )

    # Add device A
    result = await start_add_device_flow(hass, entry)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={"event_code": "0b1100cd0213c7f230010f71"},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await async_wait_for_reload(hass)

    subentry_a = next(iter(entry.subentries.values()))

    # Add device B (same protocol/type as A)
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "device"),
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={"event_code": "0b1100100118cdea02010f70"},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await async_wait_for_reload(hass)

    subentry_b_id = next(
        s.subentry_id for s in entry.subentries.values() if s != subentry_a
    )

    # Reconfigure A, picking B as the device to take over. This removes B's
    # subentry and updates A's, each of which notifies the update listener.
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_reload",
        wraps=hass.config_entries.async_reload,
    ) as mock_reload:
        result = await entry.start_subentry_reconfigure_flow(
            hass, subentry_a.subentry_id
        )
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            user_input={"replace_device": subentry_b_id},
        )
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], user_input={}
        )
        assert result["type"] is FlowResultType.ABORT
        await async_wait_for_reload(hass)

        assert mock_reload.call_count == 1


async def test_options_add_device_data_bits_conflict(hass: HomeAssistant) -> None:
    """Test data_bits masking a new device onto an already-configured one.

    The unmasked event code is validated as free before `data_bits` is even
    asked for, so the collision can only be caught once it's applied.
    """

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": None,
            "port": None,
            "device": "/dev/tty123",
            "automatic_add": False,
        },
        subentries_data=(
            {
                "data": {"event_code": "0913000022670e013970", "data_bits": 4},
                "subentry_type": "device",
                "title": "PT2262 226700",
                "unique_id": "13_0_226700",
            },
        ),
        unique_id=DOMAIN,
        version=ENTRY_VERSION,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # A different raw event code doesn't collide before data_bits is applied.
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "device"),
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={"event_code": "09130000226707013970"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "device_options"

    # Applying data_bits masks it onto the already-configured device.
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={"data_bits": 4},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "device_options"
    assert result["errors"]["data_bits"] == "already_configured_device"


async def test_options_add_duplicate_device(hass: HomeAssistant) -> None:
    """Test we can not add a duplicate device."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": None,
            "port": None,
            "device": "/dev/tty123",
            "automatic_add": False,
        },
        subentries_data=(
            {
                "data": {"event_code": "0b1100cd0213c7f230010f71"},
                "subentry_type": "device",
                "title": "AC 213c7f2:48",
                "unique_id": "11_0_213c7f2:48",
            },
        ),
        unique_id=DOMAIN,
        version=ENTRY_VERSION,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "device"),
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={"event_code": "0b1100cd0213c7f230010f71"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"]
    assert result["errors"]["event_code"] == "already_configured_device"


async def test_options_add_and_configure_device(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test we can add and reconfigure a device."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": None,
            "port": None,
            "device": "/dev/tty123",
            "automatic_add": False,
        },
        unique_id=DOMAIN,
        version=ENTRY_VERSION,
    )
    result = await start_add_device_flow(hass, entry)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={"event_code": "0913000022670e013970"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "device_options"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={
            "data_bits": 4,
            "command_on": "xyz",
            "command_off": "xyz",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "device_options"
    assert result["errors"]
    assert result["errors"]["command_on"] == "invalid_input_2262_on"
    assert result["errors"]["command_off"] == "invalid_input_2262_off"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={
            "data_bits": 4,
            "command_on": "0xE",
            "command_off": "0x7",
            "off_delay": 9,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY

    await async_wait_for_reload(hass)

    subentry = next(iter(entry.subentries.values()))
    assert subentry.data["event_code"] == "0913000022670e013970"
    assert subentry.data["off_delay"] == 9

    state = hass.states.get("binary_sensor.pt2262_226700")
    assert state
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get("friendly_name") == "PT2262 226700"

    device_entries = dr.async_entries_for_config_entry(device_registry, entry.entry_id)

    assert device_entries[0].id

    result = await entry.start_subentry_reconfigure_flow(hass, subentry.subentry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={"event_code": "0913000022670e013970"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "device_options"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={
            "data_bits": 4,
            "command_on": "0xE",
            "command_off": "0x7",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    await hass.async_block_till_done()

    subentry = entry.subentries[subentry.subentry_id]
    assert subentry.data["event_code"] == "0913000022670e013970"
    assert "off_delay" not in subentry.data


async def test_options_configure_rfy_cover_device(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test we can configure the venetion blind mode of an Rfy cover."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": None,
            "port": None,
            "device": "/dev/tty123",
            "automatic_add": False,
        },
        unique_id=DOMAIN,
        version=ENTRY_VERSION,
    )
    result = await start_add_device_flow(hass, entry)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={"event_code": "0C1a0000010203010000000000"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "device_options"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={
            "venetian_blind_mode": "EU",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY

    await async_wait_for_reload(hass)

    subentry = next(iter(entry.subentries.values()))
    assert subentry.data["event_code"] == "0C1a0000010203010000000000"
    assert subentry.data["venetian_blind_mode"] == "EU"

    device_entries = dr.async_entries_for_config_entry(device_registry, entry.entry_id)

    assert device_entries[0].id

    result = await entry.start_subentry_reconfigure_flow(hass, subentry.subentry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={"event_code": "0C1a0000010203010000000000"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "device_options"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={
            "venetian_blind_mode": "EU",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    await hass.async_block_till_done()

    subentry = entry.subentries[subentry.subentry_id]
    assert subentry.data["event_code"] == "0C1a0000010203010000000000"
    assert subentry.data["venetian_blind_mode"] == "EU"
