"""Tests for the TOLO Sauna config flow."""

from unittest.mock import Mock, patch

import pytest
from tololib import ToloCommunicationError

from homeassistant.components import dhcp
from homeassistant.components.tolo.const import DOMAIN
from homeassistant.config_entries import SOURCE_DHCP, SOURCE_USER
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

MOCK_DHCP_DATA = dhcp.DhcpServiceInfo(
    ip="127.0.0.2", macaddress="001122334455", hostname="mock_hostname"
)


@pytest.fixture(name="toloclient")
def toloclient_fixture() -> Mock:
    """Patch libraries."""
    with patch("homeassistant.components.tolo.config_flow.ToloClient") as toloclient:
        yield toloclient


@pytest.fixture
def coordinator_toloclient() -> Mock:
    """Patch ToloClient in async_setup_entry.

    Throw exception to abort entry setup and prevent socket IO. Only testing config flow.
    """
    with patch(
        "homeassistant.components.tolo.coordinator.ToloClient", side_effect=Exception
    ) as toloclient:
        yield toloclient


async def test_user_with_timed_out_host(hass: HomeAssistant, toloclient: Mock) -> None:
    """Test a user initiated config flow with provided host which times out."""
    toloclient().get_status.side_effect = ToloCommunicationError

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: "127.0.0.1"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_walkthrough(
    hass: HomeAssistant, toloclient: Mock, coordinator_toloclient: Mock
) -> None:
    """Test complete user flow with first wrong and then correct host."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    toloclient().get_status.side_effect = lambda *args, **kwargs: None

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "127.0.0.2"},
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "cannot_connect"}

    toloclient().get_status.side_effect = lambda *args, **kwargs: object()

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "127.0.0.1"},
    )

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == "TOLO Sauna"
    assert result3["data"][CONF_HOST] == "127.0.0.1"


async def test_dhcp(
    hass: HomeAssistant, toloclient: Mock, coordinator_toloclient: Mock
) -> None:
    """Test starting a flow from discovery."""
    toloclient().get_status.side_effect = lambda *args, **kwargs: object()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_DHCP}, data=MOCK_DHCP_DATA
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "TOLO Sauna"
    assert result["data"][CONF_HOST] == "127.0.0.2"
    assert result["result"].unique_id == "00:11:22:33:44:55"


async def test_dhcp_invalid_device(hass: HomeAssistant, toloclient: Mock) -> None:
    """Test starting a flow from discovery."""
    toloclient().get_status.side_effect = lambda *args, **kwargs: None

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_DHCP}, data=MOCK_DHCP_DATA
    )
    assert result["type"] is FlowResultType.ABORT
