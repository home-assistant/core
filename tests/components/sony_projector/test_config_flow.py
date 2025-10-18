"""Tests for the Sony Projector config flow."""

from __future__ import annotations

from homeassistant import config_entries
from homeassistant.components.sony_projector.client import (
    DiscoveredProjector,
    ProjectorClientError,
)
from homeassistant.components.sony_projector.const import (
    CONF_MODEL,
    CONF_SERIAL,
    CONF_TITLE,
    DEFAULT_NAME,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_manual_flow_success(
    hass: HomeAssistant,
    mock_client_class,
    mock_projector_client,
    mock_discovery,
) -> None:
    """Test configuring the projector manually."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "manual"}
    )
    assert result["type"] == FlowResultType.FORM

    user_input = {CONF_HOST: "192.0.2.11", CONF_NAME: "Living Room"}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Living Room"
    assert result["data"][CONF_HOST] == "192.0.2.11"
    assert result["data"][CONF_SERIAL] == mock_projector_client.serial
    assert result["data"][CONF_MODEL] == mock_projector_client.model
    assert mock_projector_client.async_get_state.called


async def test_manual_flow_connection_error(
    hass: HomeAssistant,
    mock_client_class,
    mock_projector_client,
    mock_discovery,
) -> None:
    """Test the manual flow handling connection errors."""

    mock_projector_client.async_get_state.side_effect = ProjectorClientError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "manual"}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.0.2.12"}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_scan_flow_success(
    hass: HomeAssistant,
    mock_client_class,
    mock_projector_client,
    mock_discovery,
) -> None:
    """Test discovering a projector and creating an entry."""

    mock_discovery.return_value = [
        DiscoveredProjector(host="192.0.2.13", model="VPL-Discovered", serial="987654")
    ]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "scan"}
    )

    assert result["type"] == FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "scan"
    assert result["progress_action"] == "listen_for_projectors"

    await hass.async_block_till_done()

    flow_id = result["flow_id"]
    result = await hass.config_entries.flow.async_configure(flow_id)
    assert result["type"] == FlowResultType.SHOW_PROGRESS_DONE

    result = await hass.config_entries.flow.async_configure(flow_id)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "scan"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.0.2.13"}
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_HOST] == "192.0.2.13"


async def test_scan_flow_no_devices(
    hass: HomeAssistant,
    mock_client_class,
    mock_projector_client,
    mock_discovery,
) -> None:
    """Test that scan handles empty results."""

    mock_discovery.return_value = []

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "scan"}
    )

    assert result["type"] == FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "scan"

    await hass.async_block_till_done()

    flow_id = result["flow_id"]
    result = await hass.config_entries.flow.async_configure(flow_id)
    assert result["type"] == FlowResultType.SHOW_PROGRESS_DONE

    result = await hass.config_entries.flow.async_configure(flow_id)

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "no_devices_found"}


async def test_import_flow(
    hass: HomeAssistant, mock_client_class, mock_projector_client
) -> None:
    """Test importing a YAML configuration."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={CONF_HOST: "192.0.2.14", CONF_NAME: DEFAULT_NAME},
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_HOST] == "192.0.2.14"


async def test_reauth_updates_entry(
    hass: HomeAssistant, mock_client_class, mock_projector_client
) -> None:
    """Test that reauth updates an existing entry."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.0.2.20",
            CONF_SERIAL: "123456",
            CONF_MODEL: "VPL-Test",
            CONF_TITLE: DEFAULT_NAME,
        },
        unique_id="123456",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_REAUTH, "entry_id": entry.entry_id},
        data=entry.data,
    )
    assert result["type"] == FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "manual"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.0.2.21"}
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


async def test_integration_discovery_flow_creates_entry(
    hass: HomeAssistant, mock_client_class, mock_projector_client
) -> None:
    """Test confirming a passively discovered projector."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
        data={
            CONF_HOST: "192.0.2.30",
            CONF_SERIAL: "ABC123",
            CONF_MODEL: "VPL-Detected",
            CONF_TITLE: "Conference Room",
        },
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_HOST] == "192.0.2.30"


async def test_integration_discovery_flow_existing_entry(
    hass: HomeAssistant, mock_client_class, mock_projector_client
) -> None:
    """Test passive discovery aborts when projector already configured."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.0.2.31",
            CONF_SERIAL: "SERIAL123",
            CONF_MODEL: "VPL-Test",
            CONF_TITLE: DEFAULT_NAME,
        },
        unique_id="SERIAL123",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
        data={
            CONF_HOST: "192.0.2.31",
            CONF_SERIAL: "SERIAL123",
            CONF_MODEL: "VPL-Test",
            CONF_TITLE: "Office",
        },
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
