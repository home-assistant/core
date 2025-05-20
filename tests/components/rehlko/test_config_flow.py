"""Test the Rehlko config flow."""

from unittest.mock import AsyncMock

from aiokem import AuthenticationCredentialsError
import pytest

from homeassistant.components.rehlko import DOMAIN
from homeassistant.config_entries import SOURCE_DHCP, SOURCE_USER
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .conftest import TEST_EMAIL, TEST_PASSWORD, TEST_SUBJECT

from tests.common import MockConfigEntry

DHCP_DISCOVERY = DhcpServiceInfo(
    ip="1.1.1.1",
    hostname="KohlerGen",
    macaddress="00146FAABBCC",
)


async def test_configure_entry(
    hass: HomeAssistant, mock_rehlko: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test we can configure the entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: TEST_EMAIL,
            CONF_PASSWORD: TEST_PASSWORD,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_EMAIL.lower()
    assert result["data"] == {
        CONF_EMAIL: TEST_EMAIL,
        CONF_PASSWORD: TEST_PASSWORD,
    }
    assert result["result"].unique_id == TEST_SUBJECT
    assert mock_setup_entry.call_count == 1


@pytest.mark.parametrize(
    ("error", "conf_error"),
    [
        (AuthenticationCredentialsError, {CONF_PASSWORD: "invalid_auth"}),
        (TimeoutError, {"base": "cannot_connect"}),
        (Exception, {"base": "unknown"}),
    ],
)
async def test_configure_entry_exceptions(
    hass: HomeAssistant,
    mock_rehlko: AsyncMock,
    error: Exception,
    conf_error: dict[str, str],
    mock_setup_entry: AsyncMock,
) -> None:
    """Test we handle a variety of exceptions and recover by adding new entry."""
    # First try to authenticate and get an error
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    mock_rehlko.authenticate.side_effect = error
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: TEST_EMAIL,
            CONF_PASSWORD: TEST_PASSWORD,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == conf_error
    assert mock_setup_entry.call_count == 0

    # Now try to authenticate again and succeed
    # This should create a new entry
    mock_rehlko.authenticate.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: TEST_EMAIL,
            CONF_PASSWORD: TEST_PASSWORD,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_EMAIL.lower()
    assert result["data"] == {
        CONF_EMAIL: TEST_EMAIL,
        CONF_PASSWORD: TEST_PASSWORD,
    }
    assert result["result"].unique_id == TEST_SUBJECT
    assert mock_setup_entry.call_count == 1


async def test_already_configured(
    hass: HomeAssistant, rehlko_config_entry: MockConfigEntry, mock_rehlko: AsyncMock
) -> None:
    """Test if entry is already configured."""
    rehlko_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: TEST_EMAIL,
            CONF_PASSWORD: TEST_PASSWORD,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth(
    hass: HomeAssistant,
    rehlko_config_entry: MockConfigEntry,
    mock_rehlko: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test reauth flow."""
    rehlko_config_entry.add_to_hass(hass)
    result = await rehlko_config_entry.start_reauth_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_PASSWORD: TEST_PASSWORD + "new",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert rehlko_config_entry.data[CONF_PASSWORD] == TEST_PASSWORD + "new"
    assert mock_setup_entry.call_count == 1


async def test_reauth_exception(
    hass: HomeAssistant,
    rehlko_config_entry: MockConfigEntry,
    mock_rehlko: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test reauth flow."""
    rehlko_config_entry.add_to_hass(hass)
    result = await rehlko_config_entry.start_reauth_flow(hass)

    mock_rehlko.authenticate.side_effect = AuthenticationCredentialsError
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_PASSWORD: TEST_PASSWORD,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"password": "invalid_auth"}

    mock_rehlko.authenticate.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_PASSWORD: TEST_PASSWORD + "new",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


async def test_dhcp_discovery(
    hass: HomeAssistant, mock_rehlko: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test we can setup from dhcp discovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_DHCP}, data=DHCP_DISCOVERY
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: TEST_EMAIL,
            CONF_PASSWORD: TEST_PASSWORD,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_dhcp_discovery_already_set_up(
    hass: HomeAssistant, rehlko_config_entry: MockConfigEntry, mock_rehlko: AsyncMock
) -> None:
    """Test DHCP discovery aborts if already set up."""
    rehlko_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_DHCP}, data=DHCP_DISCOVERY
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
