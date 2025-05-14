"""Test the wmspro config flow."""

from unittest.mock import AsyncMock, patch

import aiohttp

from homeassistant.components.wmspro.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import setup_config_entry

from tests.common import MockConfigEntry, MockDhcpServiceInfo


async def test_config_flow(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_hub_refresh: AsyncMock
) -> None:
    """Test we can handle user-input to create a config entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "wmspro.webcontrol.WebControlPro.ping",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.2.3.4",
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "1.2.3.4"
    assert result["data"] == {
        CONF_HOST: "1.2.3.4",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_config_flow_from_dhcp(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_hub_refresh: AsyncMock
) -> None:
    """Test we can handle DHCP discovery to create a config entry."""
    info = MockDhcpServiceInfo(
        ip="1.2.3.4", hostname="webcontrol", macaddress="00:11:22:33:44:55"
    )
    result = await info.start_discovery_flow(hass, DOMAIN)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "wmspro.webcontrol.WebControlPro.ping",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.2.3.4",
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "1.2.3.4"
    assert result["data"] == {
        CONF_HOST: "1.2.3.4",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_config_flow_from_dhcp_add_mac(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_hub_refresh: AsyncMock,
) -> None:
    """Test we can use DHCP discovery to add MAC address to a config entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "wmspro.webcontrol.WebControlPro.ping",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.2.3.4",
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "1.2.3.4"
    assert result["data"] == {
        CONF_HOST: "1.2.3.4",
    }
    assert len(mock_setup_entry.mock_calls) == 1
    assert hass.config_entries.async_entries(DOMAIN)[0].unique_id is None

    info = MockDhcpServiceInfo(
        ip="1.2.3.4", hostname="webcontrol", macaddress="00:11:22:33:44:55"
    )
    result = await info.start_discovery_flow(hass, DOMAIN)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert hass.config_entries.async_entries(DOMAIN)[0].unique_id == "00:11:22:33:44:55"


async def test_config_flow_from_dhcp_ip_update(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_hub_refresh: AsyncMock,
) -> None:
    """Test we can use DHCP discovery to update IP in a config entry."""
    info = MockDhcpServiceInfo(
        ip="1.2.3.4", hostname="webcontrol", macaddress="00:11:22:33:44:55"
    )
    result = await info.start_discovery_flow(hass, DOMAIN)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "wmspro.webcontrol.WebControlPro.ping",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.2.3.4",
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "1.2.3.4"
    assert result["data"] == {
        CONF_HOST: "1.2.3.4",
    }
    assert len(mock_setup_entry.mock_calls) == 1
    assert hass.config_entries.async_entries(DOMAIN)[0].unique_id == "00:11:22:33:44:55"

    info = MockDhcpServiceInfo(
        ip="5.6.7.8", hostname="webcontrol", macaddress="00:11:22:33:44:55"
    )
    result = await info.start_discovery_flow(hass, DOMAIN)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert hass.config_entries.async_entries(DOMAIN)[0].unique_id == "00:11:22:33:44:55"
    assert hass.config_entries.async_entries(DOMAIN)[0].data[CONF_HOST] == "5.6.7.8"


async def test_config_flow_from_dhcp_no_update(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_hub_refresh: AsyncMock,
) -> None:
    """Test we do not use DHCP discovery to overwrite hostname with IP in config entry."""
    info = MockDhcpServiceInfo(
        ip="1.2.3.4", hostname="webcontrol", macaddress="00:11:22:33:44:55"
    )
    result = await info.start_discovery_flow(hass, DOMAIN)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "wmspro.webcontrol.WebControlPro.ping",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "webcontrol",
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "webcontrol"
    assert result["data"] == {
        CONF_HOST: "webcontrol",
    }
    assert len(mock_setup_entry.mock_calls) == 1
    assert hass.config_entries.async_entries(DOMAIN)[0].unique_id == "00:11:22:33:44:55"

    info = MockDhcpServiceInfo(
        ip="5.6.7.8", hostname="webcontrol", macaddress="00:11:22:33:44:55"
    )
    result = await info.start_discovery_flow(hass, DOMAIN)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert hass.config_entries.async_entries(DOMAIN)[0].unique_id == "00:11:22:33:44:55"
    assert hass.config_entries.async_entries(DOMAIN)[0].data[CONF_HOST] == "webcontrol"


async def test_config_flow_ping_failed(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_hub_refresh: AsyncMock
) -> None:
    """Test we handle ping failed error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "wmspro.webcontrol.WebControlPro.ping",
        return_value=False,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.2.3.4",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    with patch(
        "wmspro.webcontrol.WebControlPro.ping",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.2.3.4",
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "1.2.3.4"
    assert result["data"] == {
        CONF_HOST: "1.2.3.4",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_config_flow_cannot_connect(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_hub_refresh: AsyncMock
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "wmspro.webcontrol.WebControlPro.ping",
        side_effect=aiohttp.ClientError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.2.3.4",
            },
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    with patch(
        "wmspro.webcontrol.WebControlPro.ping",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.2.3.4",
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "1.2.3.4"
    assert result["data"] == {
        CONF_HOST: "1.2.3.4",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_config_flow_unknown_error(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_hub_refresh: AsyncMock
) -> None:
    """Test we handle an unknown error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "wmspro.webcontrol.WebControlPro.ping",
        side_effect=RuntimeError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.2.3.4",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}

    with patch(
        "wmspro.webcontrol.WebControlPro.ping",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.2.3.4",
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "1.2.3.4"
    assert result["data"] == {
        CONF_HOST: "1.2.3.4",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_config_flow_duplicate_entries(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hub_ping: AsyncMock,
    mock_dest_refresh: AsyncMock,
    mock_hub_configuration_test: AsyncMock,
) -> None:
    """Test we prevent creation of duplicate config entries."""
    await setup_config_entry(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "5.6.7.8",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


async def test_config_flow_multiple_entries(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hub_ping: AsyncMock,
    mock_dest_refresh: AsyncMock,
    mock_hub_configuration_test: AsyncMock,
    mock_hub_configuration_prod_awning_dimmer: AsyncMock,
) -> None:
    """Test we allow creation of different config entries."""
    await setup_config_entry(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    mock_hub_configuration_prod_awning_dimmer.return_value = (
        mock_hub_configuration_test.return_value
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "5.6.7.8",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "5.6.7.8"
    assert result["data"] == {
        CONF_HOST: "5.6.7.8",
    }
    assert len(hass.config_entries.async_entries(DOMAIN)) == 2
