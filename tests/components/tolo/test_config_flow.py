"""Tests for the TOLO Sauna config flow."""

from unittest.mock import Mock, patch

import pytest
from tololib import ToloCommunicationError

from homeassistant.components.tolo.const import DOMAIN
from homeassistant.config_entries import SOURCE_DHCP, SOURCE_USER
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from tests.common import MockConfigEntry

MOCK_DHCP_DATA = DhcpServiceInfo(
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


@pytest.fixture(name="config_entry")
async def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return a MockConfigEntry for testing."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="TOLO Steam Bath",
        entry_id="1",
        data={
            CONF_HOST: "127.0.0.1",
        },
    )
    config_entry.add_to_hass(hass)

    return config_entry


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

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "127.0.0.2"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}

    toloclient().get_status.side_effect = lambda *args, **kwargs: object()

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "127.0.0.1"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "TOLO Sauna"
    assert result["data"][CONF_HOST] == "127.0.0.1"


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


async def test_reconfigure_walkthrough(
    hass: HomeAssistant,
    toloclient: Mock,
    coordinator_toloclient: Mock,
    config_entry: MockConfigEntry,
) -> None:
    """Test a reconfigure flow without problems."""
    result = await config_entry.start_reconfigure_flow(hass)

    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "127.0.0.4"}
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert config_entry.data[CONF_HOST] == "127.0.0.4"


async def test_reconfigure_error_then_fix(
    hass: HomeAssistant,
    toloclient: Mock,
    coordinator_toloclient: Mock,
    config_entry: MockConfigEntry,
) -> None:
    """Test a reconfigure flow which first fails and then recovers."""
    result = await config_entry.start_reconfigure_flow(hass)
    assert result["step_id"] == "user"

    toloclient().get_status.side_effect = ToloCommunicationError
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "127.0.0.5"}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"]["base"] == "cannot_connect"

    toloclient().get_status.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "127.0.0.4"}
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert config_entry.data[CONF_HOST] == "127.0.0.4"


async def test_reconfigure_duplicate_ip(
    hass: HomeAssistant,
    toloclient: Mock,
    coordinator_toloclient: Mock,
    config_entry: MockConfigEntry,
) -> None:
    """Test a reconfigure flow where the user is trying to have to entries with the same IP."""
    config_entry2 = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.6"}, unique_id="second_entry"
    )
    config_entry2.add_to_hass(hass)

    result = await config_entry.start_reconfigure_flow(hass)
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "127.0.0.6"}
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    assert config_entry.data[CONF_HOST] == "127.0.0.1"
