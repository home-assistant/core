"""Test the Bluesound config flow."""

from unittest.mock import AsyncMock

from pyblu.errors import PlayerUnreachableError

from homeassistant.components.bluesound.const import DOMAIN
from homeassistant.components.zeroconf import ZeroconfServiceInfo
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import PlayerMocks

from tests.common import MockConfigEntry


async def test_user_flow_success(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, player_mocks: PlayerMocks
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
    assert result["title"] == "player-name1111"
    assert result["data"] == {CONF_HOST: "1.1.1.1", CONF_PORT: 11000}
    assert result["result"].unique_id == "ff:ff:01:01:01:01-11000"

    mock_setup_entry.assert_called_once()


async def test_user_flow_cannot_connect(
    hass: HomeAssistant,
    player_mocks: PlayerMocks,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    player_mocks.player_data.sync_status_long_polling_mock.set_error(
        PlayerUnreachableError("Player not reachable")
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

    player_mocks.player_data.sync_status_long_polling_mock.set_error(None)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "1.1.1.1",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "player-name1111"
    assert result["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_PORT: 11000,
    }

    mock_setup_entry.assert_called_once()


async def test_user_flow_aleady_configured(
    hass: HomeAssistant,
    player_mocks: PlayerMocks,
    config_entry: MockConfigEntry,
) -> None:
    """Test we handle already configured."""
    config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "1.1.1.2",
            CONF_PORT: 11000,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    assert config_entry.data[CONF_HOST] == "1.1.1.2"

    player_mocks.player_data_for_already_configured.player.sync_status.assert_called_once()


async def test_import_flow_success(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, player_mocks: PlayerMocks
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_HOST: "1.1.1.1", CONF_PORT: 11000},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "player-name1111"
    assert result["data"] == {CONF_HOST: "1.1.1.1", CONF_PORT: 11000}
    assert result["result"].unique_id == "ff:ff:01:01:01:01-11000"

    mock_setup_entry.assert_called_once()
    player_mocks.player_data.player.sync_status.assert_called_once()


async def test_import_flow_cannot_connect(
    hass: HomeAssistant, player_mocks: PlayerMocks
) -> None:
    """Test we handle cannot connect error."""
    player_mocks.player_data.player.sync_status.side_effect = PlayerUnreachableError(
        "Player not reachable"
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_HOST: "1.1.1.1", CONF_PORT: 11000},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"

    player_mocks.player_data.player.sync_status.assert_called_once()


async def test_import_flow_already_configured(
    hass: HomeAssistant,
    player_mocks: PlayerMocks,
    config_entry: MockConfigEntry,
) -> None:
    """Test we handle already configured."""
    config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_HOST: "1.1.1.2", CONF_PORT: 11000},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    player_mocks.player_data_for_already_configured.player.sync_status.assert_called_once()


async def test_zeroconf_flow_success(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, player_mocks: PlayerMocks
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZeroconfServiceInfo(
            ip_address="1.1.1.1",
            ip_addresses=["1.1.1.1"],
            port=11000,
            hostname="player-name1111",
            type="_musc._tcp.local.",
            name="player-name._musc._tcp.local.",
            properties={},
        ),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"

    mock_setup_entry.assert_not_called()
    player_mocks.player_data.player.sync_status.assert_called_once()

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "player-name1111"
    assert result["data"] == {CONF_HOST: "1.1.1.1", CONF_PORT: 11000}
    assert result["result"].unique_id == "ff:ff:01:01:01:01-11000"

    mock_setup_entry.assert_called_once()


async def test_zeroconf_flow_cannot_connect(
    hass: HomeAssistant, player_mocks: PlayerMocks
) -> None:
    """Test we handle cannot connect error."""
    player_mocks.player_data.player.sync_status.side_effect = PlayerUnreachableError(
        "Player not reachable"
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZeroconfServiceInfo(
            ip_address="1.1.1.1",
            ip_addresses=["1.1.1.1"],
            port=11000,
            hostname="player-name1111",
            type="_musc._tcp.local.",
            name="player-name._musc._tcp.local.",
            properties={},
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"

    player_mocks.player_data.player.sync_status.assert_called_once()


async def test_zeroconf_flow_already_configured(
    hass: HomeAssistant,
    player_mocks: PlayerMocks,
    config_entry: MockConfigEntry,
) -> None:
    """Test we handle already configured and update the host."""
    config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZeroconfServiceInfo(
            ip_address="1.1.1.2",
            ip_addresses=["1.1.1.2"],
            port=11000,
            hostname="player-name1112",
            type="_musc._tcp.local.",
            name="player-name._musc._tcp.local.",
            properties={},
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    assert config_entry.data[CONF_HOST] == "1.1.1.2"

    player_mocks.player_data_for_already_configured.player.sync_status.assert_called_once()
