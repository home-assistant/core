"""Test the Powerwall config flow."""

from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from tesla_powerwall import (
    AccessDeniedError,
    MissingAttributeError,
    PowerwallUnreachableError,
)

from homeassistant import config_entries
from homeassistant.components import dhcp
from homeassistant.components.powerwall.const import DOMAIN
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import homeassistant.util.dt as dt_util

from .mocks import (
    MOCK_GATEWAY_DIN,
    _mock_powerwall_side_effect,
    _mock_powerwall_site_name,
    _mock_powerwall_with_fixtures,
)

from tests.common import MockConfigEntry, async_fire_time_changed

VALID_CONFIG = {CONF_IP_ADDRESS: "1.2.3.4", CONF_PASSWORD: "00GGX"}


async def test_form_source_user(hass: HomeAssistant) -> None:
    """Test we get config flow setup form as a user."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    mock_powerwall = await _mock_powerwall_site_name(hass, "MySite")

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
    assert result2["title"] == "MySite"
    assert result2["data"] == VALID_CONFIG
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize("exc", (PowerwallUnreachableError, TimeoutError))
async def test_form_cannot_connect(hass: HomeAssistant, exc: Exception) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_powerwall = await _mock_powerwall_side_effect(site_info=exc)

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


async def test_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_powerwall = await _mock_powerwall_side_effect(
        site_info=AccessDeniedError("any")
    )

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


async def test_form_unknown_exeption(hass: HomeAssistant) -> None:
    """Test we handle an unknown exception."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_powerwall = await _mock_powerwall_side_effect(site_info=ValueError)

    with patch(
        "homeassistant.components.powerwall.config_flow.Powerwall",
        return_value=mock_powerwall,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], VALID_CONFIG
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "unknown"}


async def test_form_wrong_version(hass: HomeAssistant) -> None:
    """Test we can handle wrong version error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_powerwall = await _mock_powerwall_side_effect(
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


async def test_already_configured(hass: HomeAssistant) -> None:
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


async def test_already_configured_with_ignored(hass: HomeAssistant) -> None:
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


async def test_dhcp_discovery_manual_configure(hass: HomeAssistant) -> None:
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


async def test_dhcp_discovery_auto_configure(hass: HomeAssistant) -> None:
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


async def test_dhcp_discovery_cannot_connect(hass: HomeAssistant) -> None:
    """Test we can process the discovery from dhcp and we cannot connect."""
    mock_powerwall = await _mock_powerwall_side_effect(
        site_info=PowerwallUnreachableError
    )

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


async def test_form_reauth(hass: HomeAssistant) -> None:
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


async def test_dhcp_discovery_update_ip_address(hass: HomeAssistant) -> None:
    """Test we can update the ip address from dhcp."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=VALID_CONFIG,
        unique_id=MOCK_GATEWAY_DIN,
    )
    entry.add_to_hass(hass)
    mock_powerwall = MagicMock(login=MagicMock(side_effect=PowerwallUnreachableError))
    mock_powerwall.__aenter__.return_value = mock_powerwall

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


async def test_dhcp_discovery_does_not_update_ip_when_auth_fails(
    hass: HomeAssistant,
) -> None:
    """Test we do not switch to another interface when auth is failing."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=VALID_CONFIG,
        unique_id=MOCK_GATEWAY_DIN,
    )
    entry.add_to_hass(hass)
    mock_powerwall = MagicMock(login=MagicMock(side_effect=AccessDeniedError("any")))

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
    assert entry.data[CONF_IP_ADDRESS] == "1.2.3.4"


async def test_dhcp_discovery_does_not_update_ip_when_auth_successful(
    hass: HomeAssistant,
) -> None:
    """Test we do not switch to another interface when auth is successful."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=VALID_CONFIG,
        unique_id=MOCK_GATEWAY_DIN,
    )
    entry.add_to_hass(hass)
    mock_powerwall = MagicMock(login=MagicMock(return_value=True))

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
    assert entry.data[CONF_IP_ADDRESS] == "1.2.3.4"


async def test_dhcp_discovery_updates_unique_id(hass: HomeAssistant) -> None:
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


async def test_dhcp_discovery_updates_unique_id_when_entry_is_failed(
    hass: HomeAssistant,
) -> None:
    """Test we can update the unique id from dhcp in a failed state."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=VALID_CONFIG,
        unique_id="1.2.3.4",
    )
    entry.add_to_hass(hass)
    entry.state = config_entries.ConfigEntryState.SETUP_ERROR
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


async def test_discovered_wifi_does_not_update_ip_if_is_still_online(
    hass: HomeAssistant,
) -> None:
    """Test a discovery does not update the ip unless the powerwall at the old ip is offline."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=VALID_CONFIG,
        unique_id=MOCK_GATEWAY_DIN,
    )
    entry.add_to_hass(hass)
    mock_powerwall = await _mock_powerwall_with_fixtures(hass)

    with patch(
        "homeassistant.components.powerwall.config_flow.Powerwall",
        return_value=mock_powerwall,
    ), patch(
        "homeassistant.components.powerwall.Powerwall", return_value=mock_powerwall
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=dhcp.DhcpServiceInfo(
                ip="1.2.3.5",
                macaddress="AA:BB:CC:DD:EE:FF",
                hostname=MOCK_GATEWAY_DIN.lower(),
            ),
        )
        await hass.async_block_till_done()
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_IP_ADDRESS] == "1.2.3.4"


async def test_discovered_wifi_does_not_update_ip_online_but_access_denied(
    hass: HomeAssistant,
) -> None:
    """Test a discovery does not update the ip unless the powerwall at the old ip is offline."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=VALID_CONFIG,
        unique_id=MOCK_GATEWAY_DIN,
    )
    entry.add_to_hass(hass)
    mock_powerwall = await _mock_powerwall_with_fixtures(hass)
    mock_powerwall_no_access = await _mock_powerwall_with_fixtures(hass)
    mock_powerwall_no_access.login.side_effect = AccessDeniedError("any")

    with patch(
        "homeassistant.components.powerwall.config_flow.Powerwall",
        return_value=mock_powerwall_no_access,
    ), patch(
        "homeassistant.components.powerwall.Powerwall", return_value=mock_powerwall
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Now mock the powerwall to be offline to force
        # the discovery flow to probe to see if its online
        # which will result in an access denied error, which
        # means its still online and we should not update the ip
        mock_powerwall.get_meters.side_effect = TimeoutError
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=60))
        await hass.async_block_till_done()

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=dhcp.DhcpServiceInfo(
                ip="1.2.3.5",
                macaddress="AA:BB:CC:DD:EE:FF",
                hostname=MOCK_GATEWAY_DIN.lower(),
            ),
        )
        await hass.async_block_till_done()
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_IP_ADDRESS] == "1.2.3.4"
