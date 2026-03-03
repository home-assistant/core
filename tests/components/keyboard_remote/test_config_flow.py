"""Tests for the Keyboard Remote config flow."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from homeassistant.components.keyboard_remote.const import (
    CONF_DEVICE_DESCRIPTOR,
    CONF_DEVICE_NAME,
    CONF_DEVICE_PATH,
    CONF_EMULATE_KEY_HOLD,
    CONF_EMULATE_KEY_HOLD_DELAY,
    CONF_EMULATE_KEY_HOLD_REPEAT,
    CONF_KEY_TYPES,
    DEFAULT_EMULATE_KEY_HOLD,
    DEFAULT_EMULATE_KEY_HOLD_DELAY,
    DEFAULT_EMULATE_KEY_HOLD_REPEAT,
    DEFAULT_KEY_TYPES,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import selector

from .conftest import (
    FAKE_BY_ID_BASENAME,
    FAKE_DEVICE_NAME,
    FAKE_DEVICE_NAME_2,
    FAKE_DEVICE_PATH,
    FAKE_DEVICE_PATH_2,
    FAKE_DEVICE_REAL_PATH,
)

from tests.common import MockConfigEntry

MOCK_SCAN_RESULT = [
    selector.SelectOptionDict(
        value=FAKE_DEVICE_PATH,
        label=f"{FAKE_DEVICE_NAME} ({FAKE_BY_ID_BASENAME})",
    ),
    selector.SelectOptionDict(
        value=FAKE_DEVICE_PATH_2,
        label=f"{FAKE_DEVICE_NAME_2} (usb-Test_Remote-event-kbd)",
    ),
]


# --- User step tests ---


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_step_shows_devices(hass: HomeAssistant) -> None:
    """Test user step shows a form with available devices."""
    with patch(
        "homeassistant.components.keyboard_remote.config_flow._scan_input_devices_sync",
        return_value=MOCK_SCAN_RESULT,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_step_creates_entry(hass: HomeAssistant) -> None:
    """Test user step creates a config entry on valid selection."""
    with patch(
        "homeassistant.components.keyboard_remote.config_flow._scan_input_devices_sync",
        return_value=MOCK_SCAN_RESULT,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

    with patch(
        "homeassistant.components.keyboard_remote.config_flow._get_device_name",
        return_value=FAKE_DEVICE_NAME,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_DEVICE_PATH: FAKE_DEVICE_PATH},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == FAKE_DEVICE_NAME
    assert result["data"] == {
        CONF_DEVICE_PATH: FAKE_DEVICE_PATH,
        CONF_DEVICE_NAME: FAKE_DEVICE_NAME,
    }
    assert result["options"] == {
        CONF_KEY_TYPES: DEFAULT_KEY_TYPES,
        CONF_EMULATE_KEY_HOLD: DEFAULT_EMULATE_KEY_HOLD,
        CONF_EMULATE_KEY_HOLD_DELAY: DEFAULT_EMULATE_KEY_HOLD_DELAY,
        CONF_EMULATE_KEY_HOLD_REPEAT: DEFAULT_EMULATE_KEY_HOLD_REPEAT,
    }


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_step_cannot_connect(hass: HomeAssistant) -> None:
    """Test user step shows error when device cannot be opened."""
    with patch(
        "homeassistant.components.keyboard_remote.config_flow._scan_input_devices_sync",
        return_value=MOCK_SCAN_RESULT,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

    with (
        patch(
            "homeassistant.components.keyboard_remote.config_flow._get_device_name",
            return_value=None,
        ),
        patch(
            "homeassistant.components.keyboard_remote.config_flow._scan_input_devices_sync",
            return_value=MOCK_SCAN_RESULT,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_DEVICE_PATH: FAKE_DEVICE_PATH},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_step_no_devices(hass: HomeAssistant) -> None:
    """Test user step aborts when no devices found."""
    with patch(
        "homeassistant.components.keyboard_remote.config_flow._scan_input_devices_sync",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_step_all_configured(hass: HomeAssistant) -> None:
    """Test user step aborts when all devices are already configured."""
    # Add an existing entry for the only device in scan results
    single_device = [MOCK_SCAN_RESULT[0]]
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=FAKE_BY_ID_BASENAME,
        data={CONF_DEVICE_PATH: FAKE_DEVICE_PATH},
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.keyboard_remote.config_flow._scan_input_devices_sync",
        return_value=single_device,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "all_devices_configured"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_step_already_configured(hass: HomeAssistant) -> None:
    """Test user step filters out already-configured devices."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=FAKE_BY_ID_BASENAME,
        data={CONF_DEVICE_PATH: FAKE_DEVICE_PATH},
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.keyboard_remote.config_flow._scan_input_devices_sync",
        return_value=MOCK_SCAN_RESULT,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

    # Should show form with only the second device (first is configured)
    assert result["type"] is FlowResultType.FORM

    # The second device can still be configured
    with patch(
        "homeassistant.components.keyboard_remote.config_flow._get_device_name",
        return_value=FAKE_DEVICE_NAME_2,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_DEVICE_PATH: FAKE_DEVICE_PATH_2},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_DEVICE_PATH] == FAKE_DEVICE_PATH_2


# --- Import step tests ---


@pytest.mark.usefixtures("mock_setup_entry")
async def test_import_with_descriptor_and_by_id(hass: HomeAssistant) -> None:
    """Test YAML import resolves descriptor to by-id path."""
    with patch(
        "homeassistant.components.keyboard_remote.config_flow._resolve_yaml_device",
        return_value=(FAKE_DEVICE_PATH, FAKE_DEVICE_NAME, FAKE_BY_ID_BASENAME),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={
                "device_descriptor": FAKE_DEVICE_REAL_PATH,
                "type": ["key_up", "key_down"],
                "emulate_key_hold": True,
                "emulate_key_hold_delay": 0.5,
                "emulate_key_hold_repeat": 0.05,
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == FAKE_DEVICE_NAME
    assert result["data"][CONF_DEVICE_PATH] == FAKE_DEVICE_PATH
    assert result["data"][CONF_DEVICE_NAME] == FAKE_DEVICE_NAME
    assert result["data"][CONF_DEVICE_DESCRIPTOR] == FAKE_DEVICE_REAL_PATH
    assert result["options"][CONF_KEY_TYPES] == ["key_up", "key_down"]
    assert result["options"][CONF_EMULATE_KEY_HOLD] is True
    assert result["options"][CONF_EMULATE_KEY_HOLD_DELAY] == 0.5
    assert result["options"][CONF_EMULATE_KEY_HOLD_REPEAT] == 0.05


@pytest.mark.usefixtures("mock_setup_entry")
async def test_import_with_name(hass: HomeAssistant) -> None:
    """Test YAML import with device_name resolves to by-id."""
    with patch(
        "homeassistant.components.keyboard_remote.config_flow._resolve_yaml_device",
        return_value=(FAKE_DEVICE_PATH, FAKE_DEVICE_NAME, FAKE_BY_ID_BASENAME),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={"device_name": FAKE_DEVICE_NAME},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_DEVICE_PATH] == FAKE_DEVICE_PATH
    assert result["data"][CONF_DEVICE_NAME] == FAKE_DEVICE_NAME


@pytest.mark.usefixtures("mock_setup_entry")
async def test_import_fallback_no_by_id(hass: HomeAssistant) -> None:
    """Test YAML import falls back to raw path when no by-id link exists."""
    with patch(
        "homeassistant.components.keyboard_remote.config_flow._resolve_yaml_device",
        return_value=(FAKE_DEVICE_REAL_PATH, FAKE_DEVICE_NAME, None),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={"device_descriptor": FAKE_DEVICE_REAL_PATH},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_DEVICE_PATH] == FAKE_DEVICE_REAL_PATH
    assert result["data"][CONF_DEVICE_DESCRIPTOR] == FAKE_DEVICE_REAL_PATH


@pytest.mark.usefixtures("mock_setup_entry")
async def test_import_fallback_name_only(hass: HomeAssistant) -> None:
    """Test YAML import with name when no by-id or device found."""
    with patch(
        "homeassistant.components.keyboard_remote.config_flow._resolve_yaml_device",
        return_value=(None, None, None),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={"device_name": FAKE_DEVICE_NAME},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == FAKE_DEVICE_NAME
    assert result["data"][CONF_DEVICE_PATH] == FAKE_DEVICE_NAME


async def test_import_cannot_identify(hass: HomeAssistant) -> None:
    """Test YAML import aborts when device cannot be identified."""
    with patch(
        "homeassistant.components.keyboard_remote.config_flow._resolve_yaml_device",
        return_value=(None, None, None),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_identify_device"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_import_already_configured(hass: HomeAssistant) -> None:
    """Test YAML import aborts when device is already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=FAKE_BY_ID_BASENAME,
        data={CONF_DEVICE_PATH: FAKE_DEVICE_PATH},
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.keyboard_remote.config_flow._resolve_yaml_device",
        return_value=(FAKE_DEVICE_PATH, FAKE_DEVICE_NAME, FAKE_BY_ID_BASENAME),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={"device_descriptor": FAKE_DEVICE_REAL_PATH},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_import_default_options(hass: HomeAssistant) -> None:
    """Test YAML import uses defaults when options not specified."""
    with patch(
        "homeassistant.components.keyboard_remote.config_flow._resolve_yaml_device",
        return_value=(FAKE_DEVICE_PATH, FAKE_DEVICE_NAME, FAKE_BY_ID_BASENAME),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={"device_descriptor": FAKE_DEVICE_REAL_PATH},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"] == {
        CONF_KEY_TYPES: DEFAULT_KEY_TYPES,
        CONF_EMULATE_KEY_HOLD: DEFAULT_EMULATE_KEY_HOLD,
        CONF_EMULATE_KEY_HOLD_DELAY: DEFAULT_EMULATE_KEY_HOLD_DELAY,
        CONF_EMULATE_KEY_HOLD_REPEAT: DEFAULT_EMULATE_KEY_HOLD_REPEAT,
    }


# --- Options flow tests ---


async def test_options_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the options flow allows changing settings."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.keyboard_remote.async_setup_entry",
        return_value=True,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_KEY_TYPES: ["key_up", "key_down", "key_hold"],
            CONF_EMULATE_KEY_HOLD: True,
            CONF_EMULATE_KEY_HOLD_DELAY: 0.5,
            CONF_EMULATE_KEY_HOLD_REPEAT: 0.05,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_KEY_TYPES: ["key_up", "key_down", "key_hold"],
        CONF_EMULATE_KEY_HOLD: True,
        CONF_EMULATE_KEY_HOLD_DELAY: 0.5,
        CONF_EMULATE_KEY_HOLD_REPEAT: 0.05,
    }


async def test_options_flow_shows_device_path(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the options flow shows the device path in description."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.keyboard_remote.async_setup_entry",
        return_value=True,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["description_placeholders"]["device_path"] == FAKE_DEVICE_PATH
