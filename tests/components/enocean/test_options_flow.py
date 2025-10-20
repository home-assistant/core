"""Tests for EnOcean options flow."""

from unittest.mock import AsyncMock, patch

from homeassistant.components.enocean.config_flow import (
    CONF_ENOCEAN_DEVICE_ID,
    CONF_ENOCEAN_DEVICE_NAME,
    CONF_ENOCEAN_DEVICE_TYPE_ID,
    CONF_ENOCEAN_DEVICES,
    CONF_ENOCEAN_SENDER_ID,
    ENOCEAN_DEVICE_TYPE_ID,
    ENOCEAN_ERROR_DEVICE_ALREADY_CONFIGURED,
    ENOCEAN_ERROR_DEVICE_NAME_EMPTY,
    ENOCEAN_ERROR_INVALID_DEVICE_ID,
    ENOCEAN_ERROR_INVALID_SENDER_ID,
)
from homeassistant.components.enocean.const import DOMAIN
from homeassistant.const import CONF_DEVICE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

TEST_DIMMER = {
    CONF_ENOCEAN_DEVICE_ID: "01:02:03:04",
    CONF_ENOCEAN_DEVICE_NAME: "Test Dimmer 1",
    CONF_ENOCEAN_DEVICE_TYPE_ID: "Eltako_FUD61NPN",
    CONF_ENOCEAN_SENDER_ID: "AB:AB:AB:AB",
}

TEST_DIMMER_EDITED = {
    CONF_ENOCEAN_DEVICE_ID: "01:02:03:04",
    CONF_ENOCEAN_DEVICE_NAME: "Test Switch 1",
    CONF_ENOCEAN_DEVICE_TYPE_ID: "A5-12-01",
    CONF_ENOCEAN_SENDER_ID: "BA:BA:BA:BA",
}

TEST_SWITCH = {
    CONF_ENOCEAN_DEVICE_ID: "01:02:03:05",
    CONF_ENOCEAN_DEVICE_NAME: "Test Switch",
    CONF_ENOCEAN_DEVICE_TYPE_ID: "A5-12-01",
    CONF_ENOCEAN_SENDER_ID: "AB:AB:AB:AB",
}

TEST_SWITCH_INVALID_ID = {
    CONF_ENOCEAN_DEVICE_ID: "01:02:03:G",
    CONF_ENOCEAN_DEVICE_NAME: "Test Switch",
    CONF_ENOCEAN_DEVICE_TYPE_ID: "A5-12-01",
    CONF_ENOCEAN_SENDER_ID: "AB:AB:AB:AB",
}

TEST_SWITCH_EMPTY_NAME = {
    CONF_ENOCEAN_DEVICE_ID: "01:02:03:05",
    CONF_ENOCEAN_DEVICE_NAME: "",
    CONF_ENOCEAN_DEVICE_TYPE_ID: "A5-12-01",
    CONF_ENOCEAN_SENDER_ID: "AB:AB:AB:AB",
}

TEST_SWITCH_INVALID_SENDER_ID = {
    CONF_ENOCEAN_DEVICE_ID: "01:02:03:05",
    CONF_ENOCEAN_DEVICE_NAME: "Test Switch",
    CONF_ENOCEAN_DEVICE_TYPE_ID: "A5-12-01",
    CONF_ENOCEAN_SENDER_ID: "AB:123:AB:AB",
}

FAKE_DONGLE_PATH = "/fake/dongle"

DONGLE_DETECT_METHOD = "homeassistant.components.enocean.dongle.detect"


async def test_menu_is_small_for_no_devices(
    hass: HomeAssistant,
) -> None:
    """Test that the menu contains only 'add device' when no device is configured."""
    mock_config_entry = MockConfigEntry(
        title="",
        domain=DOMAIN,
        data={CONF_DEVICE: FAKE_DONGLE_PATH},
        options={CONF_ENOCEAN_DEVICES: []},
    )

    result: FlowResultType | None = None

    with patch(
        "homeassistant.components.enocean.async_setup_entry",
        AsyncMock(return_value=True),
    ):
        mock_config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(
            mock_config_entry.entry_id
        )

    assert result is not None
    assert result["type"] == FlowResultType.MENU
    assert result["menu_options"] == ["add_device"]


async def test_menu_is_large_for_devices(hass: HomeAssistant) -> None:
    """Test that the menu contains 'add_device', 'select_device_to_edit' and 'delete_device' when at least one device is configured."""
    mock_config_entry = MockConfigEntry(
        title="",
        domain=DOMAIN,
        data={CONF_DEVICE: FAKE_DONGLE_PATH},
        options={CONF_ENOCEAN_DEVICES: [TEST_DIMMER]},
    )

    result: FlowResultType | None = None

    with patch(
        "homeassistant.components.enocean.async_setup_entry",
        AsyncMock(return_value=True),
    ):
        mock_config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(
            mock_config_entry.entry_id
        )

    assert result is not None
    assert result["type"] == FlowResultType.MENU
    assert result["menu_options"] == [
        "add_device",
        "select_device_to_edit",
        "delete_device",
    ]


async def test_add_device(hass: HomeAssistant) -> None:
    """Test adding a device."""
    mock_config_entry = MockConfigEntry(
        title="",
        domain=DOMAIN,
        data={CONF_DEVICE: FAKE_DONGLE_PATH},
        options={CONF_ENOCEAN_DEVICES: [TEST_DIMMER]},
    )

    result: FlowResultType | None = None

    with patch(
        "homeassistant.components.enocean.async_setup_entry",
        AsyncMock(return_value=True),
    ):
        mock_config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(
            mock_config_entry.entry_id
        )

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={"next_step_id": "add_device"}
        )

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                ENOCEAN_DEVICE_TYPE_ID: "A5-12-01",
                CONF_ENOCEAN_DEVICE_ID: "01:02:03:05",
                CONF_ENOCEAN_DEVICE_NAME: "Test Switch",
                CONF_ENOCEAN_SENDER_ID: "AB:AB:AB:AB",
            },
        )

    assert result is not None
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["result"] is True
    assert result["data"] == {CONF_ENOCEAN_DEVICES: [TEST_DIMMER, TEST_SWITCH]}


async def test_add_device_with_invalid_device_id_fails_1(hass: HomeAssistant) -> None:
    """Test that adding a device with invalid id will be prevented."""
    mock_config_entry = MockConfigEntry(
        title="",
        domain=DOMAIN,
        data={CONF_DEVICE: FAKE_DONGLE_PATH},
        options={CONF_ENOCEAN_DEVICES: [TEST_DIMMER]},
    )

    result: FlowResultType | None = None

    with patch(
        "homeassistant.components.enocean.async_setup_entry",
        AsyncMock(return_value=True),
    ):
        mock_config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(
            mock_config_entry.entry_id
        )

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={"next_step_id": "add_device"}
        )

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                ENOCEAN_DEVICE_TYPE_ID: "A5-12-01",
                CONF_ENOCEAN_DEVICE_ID: "01:G:03:05",
                CONF_ENOCEAN_DEVICE_NAME: "Test Switch",
                CONF_ENOCEAN_SENDER_ID: "AB:AB:AB:AB",
            },
        )

    assert result is not None
    assert result["type"] == FlowResultType.FORM
    assert CONF_ENOCEAN_DEVICE_ID in result["errors"]
    assert result["errors"][CONF_ENOCEAN_DEVICE_ID] == ENOCEAN_ERROR_INVALID_DEVICE_ID


async def test_add_device_with_invalid_device_id_fails_2(hass: HomeAssistant) -> None:
    """Test that adding a device with invalid id will be prevented."""
    mock_config_entry = MockConfigEntry(
        title="",
        domain=DOMAIN,
        data={CONF_DEVICE: FAKE_DONGLE_PATH},
        options={CONF_ENOCEAN_DEVICES: [TEST_DIMMER]},
    )

    result: FlowResultType | None = None

    with patch(
        "homeassistant.components.enocean.async_setup_entry",
        AsyncMock(return_value=True),
    ):
        mock_config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(
            mock_config_entry.entry_id
        )

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={"next_step_id": "add_device"}
        )

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                ENOCEAN_DEVICE_TYPE_ID: "A5-12-01",
                CONF_ENOCEAN_DEVICE_ID: "01:AAA:03:05",
                CONF_ENOCEAN_DEVICE_NAME: "Test Switch",
                CONF_ENOCEAN_SENDER_ID: "AB:AB:AB:AB",
            },
        )

    assert result is not None
    assert result["type"] == FlowResultType.FORM
    assert CONF_ENOCEAN_DEVICE_ID in result["errors"]
    assert result["errors"][CONF_ENOCEAN_DEVICE_ID] == ENOCEAN_ERROR_INVALID_DEVICE_ID


async def test_add_device_with_existing_device_id_fails(hass: HomeAssistant) -> None:
    """Test that adding a device which is already configured will be prevented."""
    mock_config_entry = MockConfigEntry(
        title="",
        domain=DOMAIN,
        data={CONF_DEVICE: FAKE_DONGLE_PATH},
        options={CONF_ENOCEAN_DEVICES: [TEST_DIMMER]},
    )

    result: FlowResultType | None = None

    with patch(
        "homeassistant.components.enocean.async_setup_entry",
        AsyncMock(return_value=True),
    ):
        mock_config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(
            mock_config_entry.entry_id
        )

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={"next_step_id": "add_device"}
        )

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                ENOCEAN_DEVICE_TYPE_ID: "A5-12-01",
                CONF_ENOCEAN_DEVICE_ID: "01:02:03:04",
                CONF_ENOCEAN_DEVICE_NAME: "Test Switch",
                CONF_ENOCEAN_SENDER_ID: "AB:AB:AB:AB",
            },
        )

    assert result is not None
    assert result["type"] == FlowResultType.FORM
    assert CONF_ENOCEAN_DEVICE_ID in result["errors"]
    assert (
        result["errors"][CONF_ENOCEAN_DEVICE_ID]
        == ENOCEAN_ERROR_DEVICE_ALREADY_CONFIGURED
    )


async def test_add_device_with_empty_name_fails(hass: HomeAssistant) -> None:
    """Test that adding a device with an empty name will be prevented."""
    mock_config_entry = MockConfigEntry(
        title="",
        domain=DOMAIN,
        data={CONF_DEVICE: FAKE_DONGLE_PATH},
        options={CONF_ENOCEAN_DEVICES: [TEST_DIMMER]},
    )

    result: FlowResultType | None = None

    with patch(
        "homeassistant.components.enocean.async_setup_entry",
        AsyncMock(return_value=True),
    ):
        mock_config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(
            mock_config_entry.entry_id
        )

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={"next_step_id": "add_device"}
        )

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                ENOCEAN_DEVICE_TYPE_ID: "A5-12-01",
                CONF_ENOCEAN_DEVICE_ID: "01:02:03:05",
                CONF_ENOCEAN_DEVICE_NAME: "  ",
                CONF_ENOCEAN_SENDER_ID: "AB:AB:AB:AB",
            },
        )

    assert result is not None
    assert result["type"] == FlowResultType.FORM
    assert CONF_ENOCEAN_DEVICE_NAME in result["errors"]
    assert result["errors"][CONF_ENOCEAN_DEVICE_NAME] == ENOCEAN_ERROR_DEVICE_NAME_EMPTY


async def test_add_device_with_invalid_sender_id_fails(hass: HomeAssistant) -> None:
    """Test that adding a device with an invalid sender id fails."""
    mock_config_entry = MockConfigEntry(
        title="",
        domain=DOMAIN,
        data={CONF_DEVICE: FAKE_DONGLE_PATH},
        options={CONF_ENOCEAN_DEVICES: [TEST_DIMMER]},
    )

    result: FlowResultType | None = None

    with patch(
        "homeassistant.components.enocean.async_setup_entry",
        AsyncMock(return_value=True),
    ):
        mock_config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(
            mock_config_entry.entry_id
        )

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={"next_step_id": "add_device"}
        )

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                ENOCEAN_DEVICE_TYPE_ID: "A5-12-01",
                CONF_ENOCEAN_DEVICE_ID: "01:02:03:05",
                CONF_ENOCEAN_DEVICE_NAME: "Test Switch",
                CONF_ENOCEAN_SENDER_ID: "AB:AB:AB",
            },
        )

    assert result is not None
    assert result["type"] == FlowResultType.FORM
    assert CONF_ENOCEAN_SENDER_ID in result["errors"]
    assert result["errors"][CONF_ENOCEAN_SENDER_ID] == ENOCEAN_ERROR_INVALID_SENDER_ID


async def test_delete_device(hass: HomeAssistant) -> None:
    """Test deleting a device."""
    mock_config_entry = MockConfigEntry(
        title="",
        domain=DOMAIN,
        data={CONF_DEVICE: FAKE_DONGLE_PATH},
        options={CONF_ENOCEAN_DEVICES: [TEST_DIMMER]},
    )

    result: FlowResultType | None = None

    with patch(
        "homeassistant.components.enocean.async_setup_entry",
        AsyncMock(return_value=True),
    ):
        mock_config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(
            mock_config_entry.entry_id
        )

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={"next_step_id": "delete_device"}
        )

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={"id": "01:02:03:04"}
        )

    assert result is not None
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["result"] is True
    assert result["data"] == {CONF_ENOCEAN_DEVICES: []}


async def test_edit_device(hass: HomeAssistant) -> None:
    """Test editing a device."""
    mock_config_entry = MockConfigEntry(
        title="",
        domain=DOMAIN,
        data={CONF_DEVICE: FAKE_DONGLE_PATH},
        options={CONF_ENOCEAN_DEVICES: [TEST_DIMMER]},
    )

    result: FlowResultType | None = None

    with patch(
        "homeassistant.components.enocean.async_setup_entry",
        AsyncMock(return_value=True),
    ):
        mock_config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(
            mock_config_entry.entry_id
        )

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={"next_step_id": "select_device_to_edit"}
        )

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={"id": "01:02:03:04"}
        )

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                ENOCEAN_DEVICE_TYPE_ID: "A5-12-01",
                CONF_ENOCEAN_DEVICE_ID: "01:02:03:04",
                CONF_ENOCEAN_DEVICE_NAME: "Test Switch 1",
                CONF_ENOCEAN_SENDER_ID: "BA:BA:BA:BA",
            },
        )

    assert result is not None
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["result"] is True
    assert result["data"] == {CONF_ENOCEAN_DEVICES: [TEST_DIMMER_EDITED]}


async def test_edit_device_with_invalid_sender_id_fails(hass: HomeAssistant) -> None:
    """Test that adding a device with invalid sender id will be prevented."""
    mock_config_entry = MockConfigEntry(
        title="",
        domain=DOMAIN,
        data={CONF_DEVICE: FAKE_DONGLE_PATH},
        options={CONF_ENOCEAN_DEVICES: [TEST_DIMMER]},
    )

    result: FlowResultType | None = None

    with patch(
        "homeassistant.components.enocean.async_setup_entry",
        AsyncMock(return_value=True),
    ):
        mock_config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(
            mock_config_entry.entry_id
        )

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={"next_step_id": "select_device_to_edit"}
        )

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={"id": "01:02:03:04"}
        )

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                ENOCEAN_DEVICE_TYPE_ID: "A5-12-01",
                CONF_ENOCEAN_DEVICE_ID: "01:02:03:04",
                CONF_ENOCEAN_DEVICE_NAME: "Test Switch 1",
                CONF_ENOCEAN_SENDER_ID: "BA:BA:BA:BZ",
            },
        )

    assert result is not None
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is not None
    assert CONF_ENOCEAN_SENDER_ID in result["errors"]
    assert result["errors"][CONF_ENOCEAN_SENDER_ID] == ENOCEAN_ERROR_INVALID_SENDER_ID


async def test_edit_device_with_empty_name_fails(hass: HomeAssistant) -> None:
    """Test that editing a device with empyt name will be prevented."""
    mock_config_entry = MockConfigEntry(
        title="",
        domain=DOMAIN,
        data={CONF_DEVICE: FAKE_DONGLE_PATH},
        options={CONF_ENOCEAN_DEVICES: [TEST_DIMMER]},
    )

    result: FlowResultType | None = None

    with patch(
        "homeassistant.components.enocean.async_setup_entry",
        AsyncMock(return_value=True),
    ):
        mock_config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(
            mock_config_entry.entry_id
        )

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={"next_step_id": "select_device_to_edit"}
        )

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={"id": "01:02:03:04"}
        )

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                ENOCEAN_DEVICE_TYPE_ID: "A5-12-01",
                CONF_ENOCEAN_DEVICE_ID: "01:02:03:04",
                CONF_ENOCEAN_DEVICE_NAME: "  ",
                CONF_ENOCEAN_SENDER_ID: "BA:BA:BA:BA",
            },
        )

    assert result is not None
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is not None
    assert CONF_ENOCEAN_DEVICE_NAME in result["errors"]
    assert result["errors"][CONF_ENOCEAN_DEVICE_NAME] == ENOCEAN_ERROR_DEVICE_NAME_EMPTY
