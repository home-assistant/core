"""Test the Altruist Sensor config flow."""

from ipaddress import ip_address
from unittest.mock import Mock, patch

from altruistclient import AltruistError

from homeassistant import config_entries
from homeassistant.components.altruist.config_flow import AltruistConfigFlow
from homeassistant.components.altruist.const import DOMAIN
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
        {"ip_address": "invalid_ip"},
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_ip"}


async def test_form_user_step_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    with patch(
        "homeassistant.components.altruist.config_flow.AltruistClient.from_ip_address",
        side_effect=AltruistError("Connection failed"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"ip_address": "192.168.1.100"},
        )

        assert result2["type"] == FlowResultType.FORM
        assert result2["errors"] == {"base": "no_device_found"}


async def test_form_user_step_success(
    hass: HomeAssistant, mock_altruist_client
) -> None:
    """Test successful user step."""
    with patch(
        "homeassistant.components.altruist.config_flow.AltruistClient.from_ip_address",
        return_value=mock_altruist_client,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"ip_address": "192.168.1.100"},
        )

        assert result2["type"] == FlowResultType.CREATE_ENTRY
        assert result2["title"] == "192.168.1.100"
        assert result2["data"] == {"ip_address": "192.168.1.100", "id": "5366960e8b18"}


async def test_form_user_step_already_configured(
    hass: HomeAssistant, mock_altruist_client
) -> None:
    """Test we abort if already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"ip_address": "192.168.1.100", "id": "5366960e8b18"},
        unique_id="5366960e8b18",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.altruist.config_flow.AltruistClient.from_ip_address",
        return_value=mock_altruist_client,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"ip_address": "192.168.1.100"},
        )

        assert result2["type"] == FlowResultType.ABORT
        assert result2["reason"] == "already_configured"


async def test_zeroconf_discovery(hass: HomeAssistant, mock_altruist_client) -> None:
    """Test zeroconf discovery."""
    discovery_info = Mock()
    discovery_info.ip_address = ip_address("192.168.1.100")

    with patch(
        "homeassistant.components.altruist.config_flow.AltruistClient.from_ip_address",
        return_value=mock_altruist_client,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=discovery_info,
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "discovery_confirm"


async def test_zeroconf_discovery_already_configured(
    hass: HomeAssistant, mock_altruist_client
) -> None:
    """Test zeroconf discovery when already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"ip_address": "192.168.1.100", "id": "5366960e8b18"},
        unique_id="5366960e8b18",
    )
    entry.add_to_hass(hass)

    discovery_info = Mock()
    discovery_info.ip_address = "192.168.1.100"

    with patch(
        "homeassistant.components.altruist.config_flow.AltruistClient.from_ip_address",
        return_value=mock_altruist_client,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=discovery_info,
        )

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "already_configured"


async def test_zeroconf_discovery_confirm(
    hass: HomeAssistant, mock_altruist_client
) -> None:
    """Test zeroconf discovery confirmation."""
    discovery_info = Mock()
    discovery_info.ip_address = "192.168.1.100"

    with patch(
        "homeassistant.components.altruist.config_flow.AltruistClient.from_ip_address",
        return_value=mock_altruist_client,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=discovery_info,
        )

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

        assert result2["type"] == FlowResultType.CREATE_ENTRY
        assert result2["title"] == "Altruist Sensor 5366960e8b18"
        assert result2["data"] == {"ip_address": "192.168.1.100", "id": "5366960e8b18"}


async def test_ip_validation_methods() -> None:
    """Test IP address validation methods."""

    flow = AltruistConfigFlow()

    # Valid IP addresses
    assert flow._is_valid_ip("192.168.1.1") is True
    assert flow._is_valid_ip("10.0.0.1") is True
    assert flow._is_valid_ip("172.16.0.1") is True
    assert flow._is_valid_ip("127.0.0.1") is True

    # Invalid IP addresses
    assert flow._is_valid_ip("256.1.1.1") is False
    assert flow._is_valid_ip("192.168.1") is False
    assert flow._is_valid_ip("not.an.ip.address") is False
    assert flow._is_valid_ip("") is False
    assert flow._is_valid_ip("192.168.1.256") is False
