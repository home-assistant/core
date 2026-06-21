"""Tests for EnOcean options flow."""

from unittest.mock import AsyncMock, patch

from homeassistant.components.enocean.const import (
    CONF_ENOCEAN_DEVICE_ID,
    CONF_ENOCEAN_DEVICE_TYPE_ID,
    CONF_ENOCEAN_DEVICES,
    CONF_ENOCEAN_SENDER_ID,
    DOMAIN,
    ENOCEAN_DEVICE_TYPE_ID,
    ENOCEAN_ERROR_DEVICE_ALREADY_CONFIGURED,
    ENOCEAN_ERROR_INVALID_DEVICE_ID,
)
from homeassistant.const import CONF_DEVICE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

# Gateway constants
FAKE_DONGLE_PATH = "/fake/dongle"
BASE_ID = "FF:80:00:00"
BASE_ID_1 = "FF:80:00:01"
BASE_ID_2 = "FF:80:00:02"

# Dimmer constants
DIMMER_ID = "01:02:03:04"
DIMMER_TYPE_ID = "EEP/A5-38-08"

# Switch constants
SWITCH_ID = "01:02:03:05"
SWITCH_TYPE_ID = "EEP/A5-12-01"

TEST_DIMMER = {
    CONF_ENOCEAN_DEVICE_ID: DIMMER_ID,
    CONF_ENOCEAN_DEVICE_TYPE_ID: DIMMER_TYPE_ID,
    CONF_ENOCEAN_SENDER_ID: BASE_ID,
}

TEST_DIMMER_EDITED = {
    CONF_ENOCEAN_DEVICE_ID: DIMMER_ID,
    CONF_ENOCEAN_DEVICE_TYPE_ID: SWITCH_TYPE_ID,
    CONF_ENOCEAN_SENDER_ID: BASE_ID_1,
}

TEST_SWITCH = {
    CONF_ENOCEAN_DEVICE_ID: SWITCH_ID,
    CONF_ENOCEAN_DEVICE_TYPE_ID: SWITCH_TYPE_ID,
    CONF_ENOCEAN_SENDER_ID: BASE_ID_2,
}


class _MockGateway:
    """Minimal gateway stub for options flow tests."""

    @property
    def base_id(self) -> str:
        return BASE_ID

    @property
    def sender_slots(self) -> list[str]:
        return [BASE_ID, BASE_ID_1, BASE_ID_2]

    def stop(self) -> None:
        """Stop the gateway."""


def _make_entry(options: dict) -> MockConfigEntry:
    return MockConfigEntry(
        title="",
        domain=DOMAIN,
        data={CONF_DEVICE: FAKE_DONGLE_PATH},
        options=options,
        version=2,
        minor_version=1,
    )


async def _setup_entry(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    with patch(
        "homeassistant.components.enocean.async_setup_entry",
        AsyncMock(return_value=True),
    ):
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    entry.runtime_data = _MockGateway()


async def test_menu_is_small_for_no_devices(hass: HomeAssistant) -> None:
    """Test that the menu contains only 'add device' when no device is configured."""
    entry = _make_entry({CONF_ENOCEAN_DEVICES: []})
    await _setup_entry(hass, entry)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == FlowResultType.MENU
    assert result["menu_options"] == ["add_device"]


async def test_menu_is_large_for_devices(hass: HomeAssistant) -> None:
    """Test that the menu contains all options when at least one device is configured."""
    entry = _make_entry({CONF_ENOCEAN_DEVICES: [TEST_DIMMER]})
    await _setup_entry(hass, entry)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == FlowResultType.MENU
    assert result["menu_options"] == [
        "add_device",
        "select_device_to_edit",
        "delete_device",
    ]


async def test_add_device(hass: HomeAssistant) -> None:
    """Test adding a device."""
    entry = _make_entry({CONF_ENOCEAN_DEVICES: [TEST_DIMMER]})
    await _setup_entry(hass, entry)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"next_step_id": "add_device"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            ENOCEAN_DEVICE_TYPE_ID: SWITCH_TYPE_ID,
            CONF_ENOCEAN_DEVICE_ID: SWITCH_ID,
            CONF_ENOCEAN_SENDER_ID: BASE_ID_2,
        },
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_ENOCEAN_DEVICES: [TEST_DIMMER, TEST_SWITCH]}


async def test_add_device_with_invalid_device_id_fails(hass: HomeAssistant) -> None:
    """Test that adding a device with a hex digit out of range is prevented."""
    entry = _make_entry({CONF_ENOCEAN_DEVICES: [TEST_DIMMER]})
    await _setup_entry(hass, entry)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"next_step_id": "add_device"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            ENOCEAN_DEVICE_TYPE_ID: SWITCH_TYPE_ID,
            CONF_ENOCEAN_DEVICE_ID: "01:FG:03:05",
            CONF_ENOCEAN_SENDER_ID: BASE_ID,
        },
    )

    assert result["type"] == FlowResultType.FORM
    assert CONF_ENOCEAN_DEVICE_ID in result["errors"]
    assert result["errors"][CONF_ENOCEAN_DEVICE_ID] == ENOCEAN_ERROR_INVALID_DEVICE_ID


async def test_add_device_with_existing_device_id_fails(hass: HomeAssistant) -> None:
    """Test that adding a device which is already configured is prevented."""
    entry = _make_entry({CONF_ENOCEAN_DEVICES: [TEST_DIMMER]})
    await _setup_entry(hass, entry)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"next_step_id": "add_device"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            ENOCEAN_DEVICE_TYPE_ID: SWITCH_TYPE_ID,
            CONF_ENOCEAN_DEVICE_ID: DIMMER_ID,
            CONF_ENOCEAN_SENDER_ID: BASE_ID,
        },
    )

    assert result["type"] == FlowResultType.FORM
    assert CONF_ENOCEAN_DEVICE_ID in result["errors"]
    assert (
        result["errors"][CONF_ENOCEAN_DEVICE_ID]
        == ENOCEAN_ERROR_DEVICE_ALREADY_CONFIGURED
    )


async def test_delete_device(hass: HomeAssistant) -> None:
    """Test deleting a device."""
    entry = _make_entry({CONF_ENOCEAN_DEVICES: [TEST_DIMMER]})
    await _setup_entry(hass, entry)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"next_step_id": "delete_device"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_ENOCEAN_DEVICE_ID: DIMMER_ID}
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_ENOCEAN_DEVICES: []}


async def test_edit_device(hass: HomeAssistant) -> None:
    """Test editing a device."""
    entry = _make_entry({CONF_ENOCEAN_DEVICES: [TEST_DIMMER]})
    await _setup_entry(hass, entry)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"next_step_id": "select_device_to_edit"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_ENOCEAN_DEVICE_ID: DIMMER_ID}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            ENOCEAN_DEVICE_TYPE_ID: SWITCH_TYPE_ID,
            CONF_ENOCEAN_DEVICE_ID: DIMMER_ID,
            CONF_ENOCEAN_SENDER_ID: BASE_ID_1,
        },
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_ENOCEAN_DEVICES: [TEST_DIMMER_EDITED]}
