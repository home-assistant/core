"""Test the Bluesound config flow."""

from unittest.mock import AsyncMock

from pyblu.errors import PlayerUnreachableError

from homeassistant.components.bluesound.const import DOMAIN
from homeassistant.components.zeroconf import ZeroconfServiceInfo
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_user_flow_success(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_player: AsyncMock
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "1.1.1.1",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "player-name"
    assert result["data"] == {CONF_HOST: "1.1.1.1", CONF_PORT: 11000}
    assert result["result"].unique_id == "00:11:22:33:44:55-11000"

    mock_setup_entry.assert_called_once()


async def test_user_flow_cannot_connect(
    hass: HomeAssistant, mock_player: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    mock_player.sync_status.side_effect = PlayerUnreachableError("Player not reachable")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "1.1.1.1",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert result["step_id"] == "user"

    mock_player.sync_status.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "1.1.1.1",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "player-name"
    assert result["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_PORT: 11000,
    }

    mock_setup_entry.assert_called_once()


async def test_user_flow_aleady_configured(
    hass: HomeAssistant,
    mock_player: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test we handle already configured."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "1.1.1.1",
            CONF_PORT: 11000,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    assert mock_config_entry.data[CONF_HOST] == "1.1.1.1"

    mock_player.sync_status.assert_called_once()


async def test_import_flow_success(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_player: AsyncMock
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_HOST: "1.1.1.1", CONF_PORT: 11000},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "player-name"
    assert result["data"] == {CONF_HOST: "1.1.1.1", CONF_PORT: 11000}
    assert result["result"].unique_id == "00:11:22:33:44:55-11000"

    mock_setup_entry.assert_called_once()
    mock_player.sync_status.assert_called_once()


async def test_import_flow_cannot_connect(
    hass: HomeAssistant, mock_player: AsyncMock
) -> None:
    """Test we handle cannot connect error."""
    mock_player.sync_status.side_effect = PlayerUnreachableError("Player not reachable")
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_HOST: "1.1.1.1", CONF_PORT: 11000},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"

    mock_player.sync_status.assert_called_once()


async def test_import_flow_already_configured(
    hass: HomeAssistant,
    mock_player: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test we handle already configured."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_HOST: "1.1.1.1", CONF_PORT: 11000},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    mock_player.sync_status.assert_called_once()


async def test_zeroconf_flow_success(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_player: AsyncMock
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

    mock_setup_entry.assert_not_called()
    mock_player.sync_status.assert_called_once()

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "player-name"
    assert result["data"] == {CONF_HOST: "1.1.1.1", CONF_PORT: 11000}
    assert result["result"].unique_id == "00:11:22:33:44:55-11000"

    mock_setup_entry.assert_called_once()


async def test_zeroconf_flow_cannot_connect(
    hass: HomeAssistant, mock_player: AsyncMock
) -> None:
    """Test we handle cannot connect error."""
    mock_player.sync_status.side_effect = PlayerUnreachableError("Player not reachable")
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

    mock_player.sync_status.assert_called_once()


async def test_zeroconf_flow_already_configured(
    hass: HomeAssistant,
    mock_player: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test we handle already configured and update the host."""
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

    assert mock_config_entry.data[CONF_HOST] == "1.1.1.1"

    mock_player.sync_status.assert_called_once()
