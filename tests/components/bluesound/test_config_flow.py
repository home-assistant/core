"""Test the Bluesound config flow."""

from unittest.mock import AsyncMock

import voluptuous as vol

from homeassistant.components.bluesound.const import DOMAIN
from homeassistant.components.zeroconf import ZeroconfServiceInfo
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_user_flow_success(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_player_sync_status: AsyncMock
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}
    assert result["step_id"] == "user"
    assert result["data_schema"] == vol.Schema(
        {
            vol.Required(CONF_HOST): str,
            vol.Optional(CONF_PORT, default=11000): int,
        }
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "1.1.1.1",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "player-name"
    assert result["data"] == {CONF_HOST: "1.1.1.1", CONF_PORT: 11000}
    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_player_sync_status.mock_calls) == 1


async def test_user_flow_cannot_connect(
    hass: HomeAssistant, mock_player_sync_status_client_connection_error: AsyncMock
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "1.1.1.1",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert result["step_id"] == "user"
    assert result["data_schema"] == vol.Schema(
        {
            vol.Required(CONF_HOST): str,
            vol.Optional(CONF_PORT, default=11000): int,
        }
    )

    assert len(mock_player_sync_status_client_connection_error.mock_calls) == 1


async def test_user_flow_aleady_configured(
    hass: HomeAssistant, mock_player_sync_status: AsyncMock
) -> None:
    """Test we handle already configured."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "1.1.1.1",
            CONF_PORT: 11000,
        },
        unique_id="00:11:22:33:44:55-11000",
    )
    mock_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "1.1.1.1",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    assert len(mock_player_sync_status.mock_calls) == 1


async def test_import_flow_success(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_player_sync_status: AsyncMock
) -> None:
    """Test we get the form."""
    hass.data[DOMAIN] = []

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_HOST: "1.1.1.1", CONF_PORT: 11000},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "player-name"
    assert result["data"] == {CONF_HOST: "1.1.1.1", CONF_PORT: 11000}

    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_player_sync_status.mock_calls) == 1


async def test_import_flow_cannot_connect(
    hass: HomeAssistant, mock_player_sync_status_client_connection_error: AsyncMock
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_HOST: "1.1.1.1", CONF_PORT: 11000},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"

    assert len(mock_player_sync_status_client_connection_error.mock_calls) == 1


async def test_import_flow_already_configured(
    hass: HomeAssistant, mock_player_sync_status: AsyncMock
) -> None:
    """Test we handle already configured."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "1.1.1.1",
            CONF_PORT: 11000,
        },
        unique_id="00:11:22:33:44:55-11000",
    )
    mock_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_HOST: "1.1.1.1", CONF_PORT: 11000},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    assert len(mock_player_sync_status.mock_calls) == 1


async def test_zeroconf_flow_success(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_player_sync_status: AsyncMock
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZeroconfServiceInfo(
            ip_address="1.1.1.1",
            ip_addresses=["1.1.1.1"],
            port=11000,
            hostname="player-name",
            type="_musc._tcp.local.",
            name="player-name._musc._tcp.local.",
            properties={},
        ),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"

    assert len(mock_setup_entry.mock_calls) == 0
    assert len(mock_player_sync_status.mock_calls) == 1


async def test_zeroconf_flow_cannot_connect(
    hass: HomeAssistant, mock_player_sync_status_client_connection_error: AsyncMock
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZeroconfServiceInfo(
            ip_address="1.1.1.1",
            ip_addresses=["1.1.1.1"],
            port=11000,
            hostname="player-name",
            type="_musc._tcp.local.",
            name="player-name._musc._tcp.local.",
            properties={},
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"

    assert len(mock_player_sync_status_client_connection_error.mock_calls) == 1


async def test_zeroconf_flow_already_configured(
    hass: HomeAssistant, mock_player_sync_status: AsyncMock
) -> None:
    """Test we handle already configured and update the host."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "2.2.2.2",
            CONF_PORT: 11000,
        },
        unique_id="00:11:22:33:44:55-11000",
    )
    mock_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZeroconfServiceInfo(
            ip_address="1.1.1.1",
            ip_addresses=["1.1.1.1"],
            port=11000,
            hostname="player-name",
            type="_musc._tcp.local.",
            name="player-name._musc._tcp.local.",
            properties={},
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    assert mock_entry.data[CONF_HOST] == "1.1.1.1"

    assert len(mock_player_sync_status.mock_calls) == 1
