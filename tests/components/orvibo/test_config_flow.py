"""Tests for the Orvibo config flow in Home Assistant core."""

import asyncio
from typing import Any
from unittest.mock import patch

from orvibo.s20 import S20Exception
import pytest
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.orvibo.const import CONF_SWITCH_LIST, DEFAULT_NAME, DOMAIN
from homeassistant.const import CONF_HOST, CONF_MAC
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_user_menu_display(hass: HomeAssistant) -> None:
    """Initial step displays the user menu correctly."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == "user"
    assert set(result["menu_options"]) == {"start_discovery", "edit"}


@pytest.mark.parametrize(
    ("user_input", "expected_mac"),
    [
        (
            {CONF_HOST: "192.168.1.2", CONF_MAC: "ac:cf:23:12:34:56"},
            "ac:cf:23:12:34:56",
        ),
        ({CONF_HOST: "192.168.1.2"}, "aa:bb:cc:dd:ee:ff"),
    ],
)
async def test_edit_flow_success(
    hass: HomeAssistant,
    mock_discover,
    mock_setup_entry,
    mock_s20,
    user_input: dict[str, Any],
    expected_mac: str,
) -> None:
    """Test manual flow succeeds with provided MAC or discovered MAC."""
    mock_discover.return_value = {"192.168.1.2": {"mac": b"\xaa\xbb\xcc\xdd\xee\xff"}}

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "edit"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == f"{DEFAULT_NAME} (192.168.1.2)"
    assert result["data"][CONF_HOST] == "192.168.1.2"
    assert result["data"][CONF_MAC] == expected_mac


@pytest.mark.parametrize(
    ("user_input", "expected_error"),
    [
        ({CONF_HOST: "192.168.1.2", CONF_MAC: "not_a_mac"}, "invalid_mac"),
        ({CONF_HOST: "192.168.1.99"}, "cannot_discover"),
        ({CONF_HOST: "192.168.1.3", CONF_MAC: "ac:cf:23:12:34:56"}, "cannot_connect"),
    ],
)
async def test_edit_flow_errors(
    hass: HomeAssistant,
    mock_s20,
    mock_discover,
    user_input: dict[str, Any],
    expected_error: str,
) -> None:
    """Test various errors in the manual (edit) step."""
    mock_discover.return_value = {}
    mock_s20.side_effect = S20Exception("Connection failed")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "edit"}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == expected_error


async def test_discovery_success(
    hass: HomeAssistant, mock_discover, mock_setup_entry
) -> None:
    """Verify discovery finds devices and completes config entry creation."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "start_discovery"}
    )
    assert result["type"] == FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "start_discovery"
    assert result["progress_action"] == "start_discovery"

    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "choose_switch"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SWITCH_LIST: "192.168.1.100"}
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == f"{DEFAULT_NAME} (192.168.1.100)"
    assert result["data"][CONF_HOST] == "192.168.1.100"
    assert result["data"][CONF_MAC] == "ac:cf:23:12:34:56"


async def test_discovery_no_devices(hass: HomeAssistant, mock_discover) -> None:
    """Discovery with no found devices should go to discovery_failed."""
    mock_discover.return_value = {}

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "start_discovery"}
    )

    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == "discovery_failed"


@pytest.mark.parametrize(
    ("import_data", "expected_mac"),
    [
        (
            {CONF_HOST: "192.168.1.5", CONF_MAC: "ac:cf:23:12:34:56"},
            "ac:cf:23:12:34:56",
        ),
        ({CONF_HOST: "192.168.1.5"}, "11:22:33:44:55:66"),
    ],
)
async def test_import_flow_success(
    hass: HomeAssistant,
    mock_discover,
    mock_setup_entry,
    mock_s20,
    import_data: dict[str, Any],
    expected_mac: str,
) -> None:
    """Test importing configuration.yaml entry succeeds with provided or discovered MAC."""
    mock_discover.return_value = {"192.168.1.5": {"mac": b"\x11\x22\x33\x44\x55\x66"}}

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=import_data
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "192.168.1.5"
    assert result["data"][CONF_MAC] == expected_mac


@pytest.mark.parametrize(
    ("import_data", "expected_reason"),
    [
        ({CONF_HOST: "192.168.1.5"}, "cannot_discover"),
        ({CONF_HOST: "192.168.1.5", CONF_MAC: "ac:cf:23:12:34:56"}, "cannot_connect"),
    ],
)
async def test_import_flow_errors(
    hass: HomeAssistant,
    mock_s20,
    mock_discover,
    import_data: dict[str, Any],
    expected_reason: str,
) -> None:
    """Test various abort errors in the import flow."""
    mock_discover.return_value = {}
    mock_s20.side_effect = S20Exception("Connection failed")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=import_data
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == expected_reason


async def test_discover_skips_existing_and_invalid_mac(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_discover
) -> None:
    """Test discovery ignores devices already configured and devices without MACs."""
    mock_config_entry.add_to_hass(hass)

    mock_discover.return_value = {
        "192.168.1.10": {"mac": b"\xaa\xbb\xcc\xdd\xee\xff"},
        "192.168.1.11": {},
        "192.168.1.12": {"mac": b"\x11\x22\x33\x44\x55\x66"},
    }

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "start_discovery"}
    )

    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "choose_switch"

    schema = result["data_schema"].schema
    dropdown_options = schema[vol.Required(CONF_SWITCH_LIST)].container

    assert "192.168.1.12" in dropdown_options
    assert "192.168.1.10" not in dropdown_options
    assert "192.168.1.11" not in dropdown_options


async def test_start_discovery_shows_progress(hass: HomeAssistant) -> None:
    """Test polling the flow while discovery is still in progress."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    async def delayed_executor_job(*args, **kwargs) -> dict[str, Any]:
        await asyncio.sleep(0.1)
        return {}

    with patch.object(hass, "async_add_executor_job", side_effect=delayed_executor_job):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "start_discovery"}
        )
        assert result["type"] == FlowResultType.SHOW_PROGRESS

        result = await hass.config_entries.flow.async_configure(result["flow_id"])

        assert result["type"] == FlowResultType.SHOW_PROGRESS
        assert result["progress_action"] == "start_discovery"

    await hass.async_block_till_done()


async def test_discovery_flow_task_exception(
    hass: HomeAssistant, mock_discover
) -> None:
    """Test the discovery process when the background task raises an error."""
    mock_discover.side_effect = S20Exception("Network timeout")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "start_discovery"}
    )

    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == "discovery_failed"
