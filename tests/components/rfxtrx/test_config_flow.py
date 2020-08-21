"""Test the Tado config flow."""
from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.rfxtrx import DOMAIN
from homeassistant.helpers.device_registry import (
    async_entries_for_config_entry,
    async_get_registry,
)

from tests.common import MockConfigEntry


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
