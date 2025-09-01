"""Test the Altruist config flow."""

from ipaddress import ip_address
from unittest.mock import AsyncMock

from homeassistant.components.altruist.const import CONF_HOST, DOMAIN
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from tests.common import MockConfigEntry

ZEROCONF_DISCOVERY = ZeroconfServiceInfo(
    ip_address=ip_address("192.168.1.100"),
    ip_addresses=[ip_address("192.168.1.100")],
    hostname="altruist-purple.local.",
    name="altruist-purple._altruist._tcp.local.",
    port=80,
    type="_altruist._tcp.local.",
    properties={
        "PATH": "/config",
    },
)


async def test_form_user_step_success(
    hass: HomeAssistant,
    mock_altruist_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test user step shows form and succeeds with valid input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.1.100"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "5366960e8b18"
    assert result["data"] == {
        CONF_HOST: "192.168.1.100",
    }
    assert result["result"].unique_id == "5366960e8b18"


async def test_form_user_step_cannot_connect_then_recovers(
    hass: HomeAssistant,
    mock_altruist_client: AsyncMock,
    mock_altruist_client_fails_once: None,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test we handle connection error and allow recovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    # First attempt triggers an error
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.1.100"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_device_found"}

    # Second attempt recovers with a valid client
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.1.100"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "5366960e8b18"
    assert result["result"].unique_id == "5366960e8b18"
    assert result["data"] == {
        CONF_HOST: "192.168.1.100",
    }


async def test_form_user_step_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_altruist_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test we abort if already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.1.100"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_zeroconf_discovery(
    hass: HomeAssistant,
    mock_altruist_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test zeroconf discovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZEROCONF_DISCOVERY,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "5366960e8b18"
    assert result["data"] == {
        CONF_HOST: "192.168.1.100",
    }
    assert result["result"].unique_id == "5366960e8b18"


async def test_zeroconf_discovery_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_altruist_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test zeroconf discovery when already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZEROCONF_DISCOVERY,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_zeroconf_discovery_cant_create_client(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_altruist_client_fails_once: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test zeroconf discovery when already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZEROCONF_DISCOVERY,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_device_found"
