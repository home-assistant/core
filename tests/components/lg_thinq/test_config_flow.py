"""Test the lgthinq config flow."""

from unittest.mock import AsyncMock

import pytest
from pytest_homeassistant.common import MockConfigEntry
from thinqconnect import ThinQAPIException

from homeassistant.components.lg_thinq.const import CONF_CONNECT_CLIENT_ID, DOMAIN
from homeassistant.config_entries import SOURCE_DHCP, SOURCE_USER
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_COUNTRY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .const import MOCK_CONNECT_CLIENT_ID, MOCK_COUNTRY, MOCK_NEW_PAT, MOCK_PAT

DHCP_DISCOVERY = DhcpServiceInfo(
    ip="1.1.1.1",
    hostname="LG_Smart_Dryer2_open",
    macaddress=dr.format_mac("34:E6:E6:11:22:33").replace(":", ""),
)


@pytest.mark.usefixtures("mock_setup_entry")
async def test_config_flow(
    hass: HomeAssistant, mock_config_thinq_api: AsyncMock, mock_uuid: AsyncMock
) -> None:
    """Test that an thinq entry is normally created."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_ACCESS_TOKEN: MOCK_PAT, CONF_COUNTRY: MOCK_COUNTRY},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_ACCESS_TOKEN: MOCK_PAT,
        CONF_COUNTRY: MOCK_COUNTRY,
        CONF_CONNECT_CLIENT_ID: MOCK_CONNECT_CLIENT_ID,
    }
    assert result["result"].unique_id == MOCK_PAT

    mock_config_thinq_api.async_get_device_list.assert_called_once()


async def test_config_flow_default_country(hass: HomeAssistant) -> None:
    """Test the country defaults to the configured Home Assistant country."""
    hass.config.country = "DE"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["data_schema"]({CONF_ACCESS_TOKEN: MOCK_PAT})[CONF_COUNTRY] == "DE"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_config_flow_invalid_pat(
    hass: HomeAssistant, mock_invalid_thinq_api: AsyncMock
) -> None:
    """Test that an thinq flow should be aborted with an invalid PAT."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_ACCESS_TOKEN: MOCK_PAT, CONF_COUNTRY: MOCK_COUNTRY},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]
    mock_invalid_thinq_api.async_get_device_list.assert_called_once()

    mock_invalid_thinq_api.async_get_device_list.side_effect = None
    mock_invalid_thinq_api.async_get_device_list.return_value = ["air_conditioner"]
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_ACCESS_TOKEN: MOCK_PAT, CONF_COUNTRY: MOCK_COUNTRY},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_config_flow_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_config_thinq_api: AsyncMock,
) -> None:
    """Test that thinq flow should be aborted when already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_ACCESS_TOKEN: MOCK_PAT, CONF_COUNTRY: MOCK_COUNTRY},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_dhcp_config_flow(
    hass: HomeAssistant, mock_config_thinq_api: AsyncMock, mock_uuid: AsyncMock
) -> None:
    """Test that a thinq entry is normally created."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_DHCP}, data=DHCP_DISCOVERY
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_ACCESS_TOKEN: MOCK_PAT, CONF_COUNTRY: MOCK_COUNTRY},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_ACCESS_TOKEN: MOCK_PAT,
        CONF_COUNTRY: MOCK_COUNTRY,
        CONF_CONNECT_CLIENT_ID: MOCK_CONNECT_CLIENT_ID,
    }
    assert result["result"].unique_id == MOCK_PAT

    mock_config_thinq_api.async_get_device_list.assert_called_once()


async def test_dhcp_config_flow_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_config_thinq_api: AsyncMock,
) -> None:
    """Test that thinq flow should be aborted when already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_DHCP}, data=DHCP_DISCOVERY
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reauth_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_config_thinq_api: AsyncMock,
) -> None:
    """Test reauthentication with a new PAT."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_ACCESS_TOKEN: MOCK_NEW_PAT}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.unique_id == MOCK_NEW_PAT
    assert mock_config_entry.data == {
        CONF_ACCESS_TOKEN: MOCK_NEW_PAT,
        CONF_COUNTRY: MOCK_COUNTRY,
        CONF_CONNECT_CLIENT_ID: MOCK_CONNECT_CLIENT_ID,
    }
    mock_config_thinq_api.async_get_device_list.assert_called_once()


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    ("code", "error"),
    [
        pytest.param("1103", "invalid_token", id="invalid_token"),
        pytest.param("1309", "not_allowed_api_again", id="not_allowed_api_again"),
        pytest.param("1302", "token_unauthorized", id="token_unauthorized"),
    ],
)
async def test_reauth_flow_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_config_thinq_api: AsyncMock,
    code: str,
    error: str,
) -> None:
    """Test reauthentication errors and recovery."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    mock_config_thinq_api.async_get_device_list.side_effect = ThinQAPIException(
        code=code, message="error", headers={}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_ACCESS_TOKEN: MOCK_PAT}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": error}

    mock_config_thinq_api.async_get_device_list.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_ACCESS_TOKEN: MOCK_NEW_PAT}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_ACCESS_TOKEN] == MOCK_NEW_PAT


async def test_reauth_flow_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_config_thinq_api: AsyncMock,
) -> None:
    """Test reauthentication aborts when the PAT belongs to another entry."""
    mock_config_entry.add_to_hass(hass)
    MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_NEW_PAT,
        data={
            CONF_ACCESS_TOKEN: MOCK_NEW_PAT,
            CONF_CONNECT_CLIENT_ID: MOCK_CONNECT_CLIENT_ID,
            CONF_COUNTRY: MOCK_COUNTRY,
        },
    ).add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_ACCESS_TOKEN: MOCK_NEW_PAT}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data[CONF_ACCESS_TOKEN] == MOCK_PAT
    mock_config_thinq_api.async_get_device_list.assert_not_called()
