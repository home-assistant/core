"""Test the Powerwall config flow."""

from unittest.mock import patch

from tesla_powerwall import (
    AccessDeniedError,
    MissingAttributeError,
    PowerwallUnreachableError,
)

from homeassistant import config_entries
from homeassistant.components import dhcp
from homeassistant.components.powerwall.const import DOMAIN
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD
from homeassistant.data_entry_flow import FlowResultType

from .mocks import (
    MOCK_GATEWAY_DIN,
    _mock_powerwall_side_effect,
    _mock_powerwall_site_name,
)

from tests.common import MockConfigEntry

VALID_CONFIG = {CONF_IP_ADDRESS: "1.2.3.4", CONF_PASSWORD: "00GGX"}


async def test_form_source_user(hass):
    """Test we get config flow setup form as a user."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    mock_powerwall = await _mock_powerwall_site_name(hass, "My site")

    with patch(
        "homeassistant.components.powerwall.config_flow.Powerwall",
        return_value=mock_powerwall,
    ), patch(
        "homeassistant.components.powerwall.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            VALID_CONFIG,
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "My site"
    assert result2["data"] == VALID_CONFIG
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_powerwall = _mock_powerwall_side_effect(site_info=PowerwallUnreachableError)

    with patch(
        "homeassistant.components.powerwall.config_flow.Powerwall",
        return_value=mock_powerwall,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            VALID_CONFIG,
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {CONF_IP_ADDRESS: "cannot_connect"}


async def test_invalid_auth(hass):
    """Test we handle invalid auth error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_powerwall = _mock_powerwall_side_effect(site_info=AccessDeniedError("any"))

    with patch(
        "homeassistant.components.powerwall.config_flow.Powerwall",
        return_value=mock_powerwall,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            VALID_CONFIG,
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {CONF_PASSWORD: "invalid_auth"}


async def test_form_unknown_exeption(hass):
    """Test we handle an unknown exception."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_powerwall = _mock_powerwall_side_effect(site_info=ValueError)

    with patch(
        "homeassistant.components.powerwall.config_flow.Powerwall",
        return_value=mock_powerwall,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], VALID_CONFIG
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "unknown"}


async def test_form_wrong_version(hass):
    """Test we can handle wrong version error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_powerwall = _mock_powerwall_side_effect(
        site_info=MissingAttributeError({}, "")
    )

    with patch(
        "homeassistant.components.powerwall.config_flow.Powerwall",
        return_value=mock_powerwall,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            VALID_CONFIG,
        )

    assert result3["type"] == "form"
    assert result3["errors"] == {"base": "wrong_version"}


async def test_already_configured(hass):
    """Test we abort when already configured."""

    config_entry = MockConfigEntry(domain=DOMAIN, data={CONF_IP_ADDRESS: "1.1.1.1"})
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=dhcp.DhcpServiceInfo(
            ip="1.1.1.1",
            macaddress="AA:BB:CC:DD:EE:FF",
            hostname="any",
        ),
    )
    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_already_configured_with_ignored(hass):
    """Test ignored entries do not break checking for existing entries."""

    config_entry = MockConfigEntry(
        domain=DOMAIN, data={}, source=config_entries.SOURCE_IGNORE
    )
    config_entry.add_to_hass(hass)

    mock_powerwall = await _mock_powerwall_site_name(hass, "Some site")

    with patch(
        "homeassistant.components.powerwall.config_flow.Powerwall",
        return_value=mock_powerwall,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=dhcp.DhcpServiceInfo(
                ip="1.1.1.1",
                macaddress="AA:BB:CC:DD:EE:FF",
                hostname="00GGX",
            ),
        )
    assert result["type"] == "form"
    assert result["errors"] is None

    with patch(
        "homeassistant.components.powerwall.config_flow.Powerwall",
        return_value=mock_powerwall,
    ), patch(
        "homeassistant.components.powerwall.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "Some site"
    assert result2["data"] == {"ip_address": "1.1.1.1", "password": "00GGX"}
    assert len(mock_setup_entry.mock_calls) == 1


async def test_dhcp_discovery_manual_configure(hass):
    """Test we can process the discovery from dhcp and manually configure."""
    mock_powerwall = await _mock_powerwall_site_name(hass, "Some site")

    with patch(
        "homeassistant.components.powerwall.config_flow.Powerwall.login",
        side_effect=AccessDeniedError("xyz"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=dhcp.DhcpServiceInfo(
                ip="1.1.1.1",
                macaddress="AA:BB:CC:DD:EE:FF",
                hostname="any",
            ),
        )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.powerwall.config_flow.Powerwall",
        return_value=mock_powerwall,
    ), patch(
        "homeassistant.components.powerwall.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            VALID_CONFIG,
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "Some site"
    assert result2["data"] == VALID_CONFIG
    assert len(mock_setup_entry.mock_calls) == 1


async def test_dhcp_discovery_auto_configure(hass):
    """Test we can process the discovery from dhcp and auto configure."""
    mock_powerwall = await _mock_powerwall_site_name(hass, "Some site")

    with patch(
        "homeassistant.components.powerwall.config_flow.Powerwall",
        return_value=mock_powerwall,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=dhcp.DhcpServiceInfo(
                ip="1.1.1.1",
                macaddress="AA:BB:CC:DD:EE:FF",
                hostname="00GGX",
            ),
        )
    assert result["type"] == "form"
    assert result["errors"] is None

    with patch(
        "homeassistant.components.powerwall.config_flow.Powerwall",
        return_value=mock_powerwall,
    ), patch(
        "homeassistant.components.powerwall.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "Some site"
    assert result2["data"] == {"ip_address": "1.1.1.1", "password": "00GGX"}
    assert len(mock_setup_entry.mock_calls) == 1


async def test_dhcp_discovery_cannot_connect(hass):
    """Test we can process the discovery from dhcp and we cannot connect."""
    mock_powerwall = _mock_powerwall_side_effect(site_info=PowerwallUnreachableError)

    with patch(
        "homeassistant.components.powerwall.config_flow.Powerwall",
        return_value=mock_powerwall,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=dhcp.DhcpServiceInfo(
                ip="1.1.1.1",
                macaddress="AA:BB:CC:DD:EE:FF",
                hostname="00GGX",
            ),
        )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_form_reauth(hass):
    """Test reauthenticate."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=VALID_CONFIG,
        unique_id=MOCK_GATEWAY_DIN,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_REAUTH, "entry_id": entry.entry_id},
        data=entry.data,
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    mock_powerwall = await _mock_powerwall_site_name(hass, "My site")

    with patch(
        "homeassistant.components.powerwall.config_flow.Powerwall",
        return_value=mock_powerwall,
    ), patch(
        "homeassistant.components.powerwall.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_PASSWORD: "new-test-password",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "abort"
    assert result2["reason"] == "reauth_successful"
    assert len(mock_setup_entry.mock_calls) == 1


async def test_dhcp_discovery_update_ip_address(hass):
    """Test we can update the ip address from dhcp."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=VALID_CONFIG,
        unique_id=MOCK_GATEWAY_DIN,
    )
    entry.add_to_hass(hass)
    mock_powerwall = await _mock_powerwall_site_name(hass, "Some site")

    with patch(
        "homeassistant.components.powerwall.config_flow.Powerwall",
        return_value=mock_powerwall,
    ), patch(
        "homeassistant.components.powerwall.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=dhcp.DhcpServiceInfo(
                ip="1.1.1.1",
                macaddress="AA:BB:CC:DD:EE:FF",
                hostname=MOCK_GATEWAY_DIN.lower(),
            ),
        )
        await hass.async_block_till_done()
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_IP_ADDRESS] == "1.1.1.1"


async def test_dhcp_discovery_updates_unique_id(hass):
    """Test we can update the unique id from dhcp."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=VALID_CONFIG,
        unique_id="1.2.3.4",
    )
    entry.add_to_hass(hass)
    mock_powerwall = await _mock_powerwall_site_name(hass, "Some site")

    with patch(
        "homeassistant.components.powerwall.config_flow.Powerwall",
        return_value=mock_powerwall,
    ), patch(
        "homeassistant.components.powerwall.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=dhcp.DhcpServiceInfo(
                ip="1.2.3.4",
                macaddress="AA:BB:CC:DD:EE:FF",
                hostname=MOCK_GATEWAY_DIN.lower(),
            ),
        )
        await hass.async_block_till_done()
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_IP_ADDRESS] == "1.2.3.4"
    assert entry.unique_id == MOCK_GATEWAY_DIN
