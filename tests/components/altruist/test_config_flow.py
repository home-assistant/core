"""Test the Altruist Sensor config flow."""

from ipaddress import ip_address
from unittest.mock import Mock, patch

from altruistclient import AltruistError

from homeassistant import config_entries
from homeassistant.components.altruist.const import (
    CONF_DEVICE_ID,
    CONF_IP_ADDRESS,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_form_user_step(hass: HomeAssistant) -> None:
    """Test we get the form for user step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}


async def test_form_user_step_invalid_ip(hass: HomeAssistant) -> None:
    """Test we handle invalid IP address."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_IP_ADDRESS: "invalid_ip"},
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_ip"}


async def test_form_user_step_cannot_connect_then_recovers(
    hass: HomeAssistant, mock_altruist_client
) -> None:
    """Test we handle connection error and allow recovery."""
    with patch(
        "homeassistant.components.altruist.config_flow.AltruistClient.from_ip_address",
        side_effect=[
            AltruistError("Connection failed"),
            mock_altruist_client,
        ],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )

        # First attempt triggers an error
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"ip_address": "192.168.1.100"},
        )

        assert result2["type"] is FlowResultType.FORM
        assert result2["errors"] == {"base": "no_device_found"}

        # Second attempt recovers with a valid client
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"ip_address": "192.168.1.100"},
        )

        assert result3["type"] is FlowResultType.CREATE_ENTRY
        assert result3["title"] == "Altruist 5366960e8b18"
        assert result3["data"] == {
            CONF_IP_ADDRESS: "192.168.1.100",
            CONF_DEVICE_ID: "5366960e8b18",
        }


async def test_form_user_step_success(
    hass: HomeAssistant, mock_altruist_client
) -> None:
    """Test successful user step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_IP_ADDRESS: "192.168.1.100"},
    )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Altruist 5366960e8b18"
    assert result2["data"] == {
        CONF_IP_ADDRESS: "192.168.1.100",
        CONF_DEVICE_ID: "5366960e8b18",
    }


async def test_form_user_step_already_configured(
    hass: HomeAssistant, mock_altruist_client
) -> None:
    """Test we abort if already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_IP_ADDRESS: "192.168.1.100", CONF_DEVICE_ID: "5366960e8b18"},
        unique_id="5366960e8b18",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_IP_ADDRESS: "192.168.1.100"},
    )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_zeroconf_discovery(hass: HomeAssistant, mock_altruist_client) -> None:
    """Test zeroconf discovery."""
    discovery_info = Mock()
    discovery_info.ip_address = ip_address("192.168.1.100")

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"


async def test_zeroconf_discovery_already_configured(
    hass: HomeAssistant, mock_altruist_client
) -> None:
    """Test zeroconf discovery when already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_IP_ADDRESS: "192.168.1.100", CONF_DEVICE_ID: "5366960e8b18"},
        unique_id="5366960e8b18",
    )
    entry.add_to_hass(hass)

    discovery_info = Mock()
    discovery_info.ip_address = "192.168.1.100"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_zeroconf_discovery_confirm(
    hass: HomeAssistant, mock_altruist_client
) -> None:
    """Test zeroconf discovery confirmation."""
    discovery_info = Mock()
    discovery_info.ip_address = "192.168.1.100"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Altruist 5366960e8b18"
    assert result2["data"] == {
        CONF_IP_ADDRESS: "192.168.1.100",
        CONF_DEVICE_ID: "5366960e8b18",
    }
