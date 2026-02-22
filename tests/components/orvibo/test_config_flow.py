"""Tests for the Orvibo config flow in Home Assistant core."""

import asyncio
from unittest.mock import patch

from orvibo.s20 import S20Exception
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


async def test_edit_flow_valid_input(
    hass: HomeAssistant, mock_s20, mock_setup_entry
) -> None:
    """Test manual (edit) flow completes successfully with valid inputs."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "edit"}
    )
    assert result["step_id"] == "edit"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.1.2", CONF_MAC: "ac:cf:23:12:34:56"},
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == f"{DEFAULT_NAME} (192.168.1.2)"
    assert result["data"][CONF_HOST] == "192.168.1.2"
    assert result["data"][CONF_MAC] == "ac:cf:23:12:34:56"


async def test_edit_flow_invalid_mac(hass: HomeAssistant) -> None:
    """Invalid MAC input shows error in edit step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "edit"}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.1.2", CONF_MAC: "not_a_mac"},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_mac"


async def test_edit_flow_connection_error(hass: HomeAssistant, mock_s20) -> None:
    """Connection failure in edit step results in form error."""
    mock_s20.side_effect = S20Exception("Connection failed")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "edit"}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.1.3", CONF_MAC: "ac:cf:23:12:34:56"},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"


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


async def test_import_flow_success(
    hass: HomeAssistant, mock_s20, mock_setup_entry
) -> None:
    """Test importing configuration.yaml entry succeeds."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={CONF_HOST: "192.168.1.5", CONF_MAC: "AC:CF:23:12:34:56"},
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "192.168.1.5"
    assert result["data"][CONF_MAC] == "ac:cf:23:12:34:56"


async def test_import_flow_connection_error(hass: HomeAssistant, mock_s20) -> None:
    """Import flow should abort if connection fails."""
    mock_s20.side_effect = S20Exception("Connection failed")

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={CONF_HOST: "192.168.1.5", CONF_MAC: "ac:cf:23:12:34:56"},
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


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

    async def delayed_executor_job(*args, **kwargs):
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
