"""Test the homewizard config flow."""

from ipaddress import ip_address
from unittest.mock import AsyncMock, MagicMock

from homewizard_energy.errors import DisabledError, RequestError, UnsupportedError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant import config_entries
from homeassistant.components import dhcp, zeroconf
from homeassistant.components.homewizard.const import DOMAIN
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_setup_entry")
async def test_manual_flow_works(
    hass: HomeAssistant,
    mock_homewizardenergy: MagicMock,
    mock_setup_entry: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config flow accepts user configuration."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_IP_ADDRESS: "2.2.2.2"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result == snapshot

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(mock_homewizardenergy.close.mock_calls) == 1
    assert len(mock_homewizardenergy.device.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_homewizardenergy", "mock_setup_entry")
async def test_discovery_flow_works(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Test discovery setup flow works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address("127.0.0.1"),
            ip_addresses=[ip_address("127.0.0.1")],
            port=80,
            hostname="p1meter-ddeeff.local.",
            type="",
            name="",
            properties={
                "api_enabled": "1",
                "path": "/api/v1",
                "product_name": "Energy Socket",
                "product_type": "HWE-SKT",
                "serial": "5c2fafabcdef",
            },
        ),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=None
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"ip_address": "127.0.0.1"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result == snapshot


@pytest.mark.usefixtures("mock_homewizardenergy")
async def test_discovery_flow_during_onboarding(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_onboarding: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test discovery setup flow during onboarding."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address("127.0.0.1"),
            ip_addresses=[ip_address("127.0.0.1")],
            port=80,
            hostname="p1meter-ddeeff.local.",
            type="mock_type",
            name="mock_name",
            properties={
                "api_enabled": "1",
                "path": "/api/v1",
                "product_name": "P1 meter",
                "product_type": "HWE-P1",
                "serial": "5c2fafabcdef",
            },
        ),
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result == snapshot

    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_onboarding.mock_calls) == 1


async def test_discovery_flow_during_onboarding_disabled_api(
    hass: HomeAssistant,
    mock_homewizardenergy: MagicMock,
    mock_setup_entry: AsyncMock,
    mock_onboarding: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test discovery setup flow during onboarding with a disabled API."""
    mock_homewizardenergy.device.side_effect = DisabledError

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address("127.0.0.1"),
            ip_addresses=[ip_address("127.0.0.1")],
            port=80,
            hostname="p1meter-ddeeff.local.",
            type="mock_type",
            name="mock_name",
            properties={
                "api_enabled": "0",
                "path": "/api/v1",
                "product_name": "P1 meter",
                "product_type": "HWE-P1",
                "serial": "5c2fafabcdef",
            },
        ),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"
    assert result["errors"] == {"base": "api_not_enabled"}

    # We are onboarded, user enabled API again and picks up from discovery/config flow
    mock_homewizardenergy.device.side_effect = None
    mock_onboarding.return_value = True

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"ip_address": "127.0.0.1"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result == snapshot

    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_onboarding.mock_calls) == 1


async def test_discovery_disabled_api(
    hass: HomeAssistant,
    mock_homewizardenergy: MagicMock,
) -> None:
    """Test discovery detecting disabled api."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address("127.0.0.1"),
            ip_addresses=[ip_address("127.0.0.1")],
            port=80,
            hostname="p1meter-ddeeff.local.",
            type="",
            name="",
            properties={
                "api_enabled": "0",
                "path": "/api/v1",
                "product_name": "P1 meter",
                "product_type": "HWE-P1",
                "serial": "5c2fafabcdef",
            },
        ),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    mock_homewizardenergy.device.side_effect = DisabledError

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"ip_address": "127.0.0.1"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "api_not_enabled"}


async def test_discovery_missing_data_in_service_info(hass: HomeAssistant) -> None:
    """Test discovery detecting missing discovery info."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address("127.0.0.1"),
            ip_addresses=[ip_address("127.0.0.1")],
            port=80,
            hostname="p1meter-ddeeff.local.",
            type="",
            name="",
            properties={
                # "api_enabled": "1", --> removed
                "path": "/api/v1",
                "product_name": "P1 meter",
                "product_type": "HWE-P1",
                "serial": "5c2fafabcdef",
            },
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_discovery_parameters"


async def test_discovery_invalid_api(hass: HomeAssistant) -> None:
    """Test discovery detecting invalid_api."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address("127.0.0.1"),
            ip_addresses=[ip_address("127.0.0.1")],
            port=80,
            hostname="p1meter-ddeeff.local.",
            type="",
            name="",
            properties={
                "api_enabled": "1",
                "path": "/api/not_v1",
                "product_name": "P1 meter",
                "product_type": "HWE-P1",
                "serial": "5c2fafabcdef",
            },
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unsupported_api_version"


async def test_dhcp_discovery_updates_entry(
    hass: HomeAssistant,
    mock_homewizardenergy: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test DHCP discovery updates config entries."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=dhcp.DhcpServiceInfo(
            ip="1.0.0.127",
            hostname="HW-p1meter-aabbcc",
            macaddress="5c2fafabcdef",
        ),
    )

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "already_configured"
    assert mock_config_entry.data[CONF_IP_ADDRESS] == "1.0.0.127"


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    ("exception"),
    [(DisabledError), (RequestError)],
)
async def test_dhcp_discovery_updates_entry_fails(
    hass: HomeAssistant,
    mock_homewizardenergy: MagicMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
) -> None:
    """Test DHCP discovery updates config entries, but fails to connect."""
    mock_homewizardenergy.device.side_effect = exception
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=dhcp.DhcpServiceInfo(
            ip="1.0.0.127",
            hostname="HW-p1meter-aabbcc",
            macaddress="5c2fafabcdef",
        ),
    )

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "unknown"


async def test_dhcp_discovery_ignores_unknown(
    hass: HomeAssistant,
    mock_homewizardenergy: MagicMock,
) -> None:
    """Test DHCP discovery is only used for updates.

    Anything else will just abort the flow.
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=dhcp.DhcpServiceInfo(
            ip="127.0.0.1",
            hostname="HW-p1meter-aabbcc",
            macaddress="5c2fafabcdef",
        ),
    )

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "unknown"


async def test_discovery_flow_updates_new_ip(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test discovery setup updates new config data."""
    mock_config_entry.add_to_hass(hass)

    # preflight check, see if the ip address is already in use
    assert mock_config_entry.data[CONF_IP_ADDRESS] == "127.0.0.1"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address("1.0.0.127"),
            ip_addresses=[ip_address("1.0.0.127")],
            port=80,
            hostname="p1meter-ddeeff.local.",
            type="",
            name="",
            properties={
                "api_enabled": "1",
                "path": "/api/v1",
                "product_name": "P1 Meter",
                "product_type": "HWE-P1",
                "serial": "5c2fafabcdef",
            },
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    assert mock_config_entry.data[CONF_IP_ADDRESS] == "1.0.0.127"


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    ("exception", "reason"),
    [(DisabledError, "api_not_enabled"), (RequestError, "network_error")],
)
async def test_error_flow(
    hass: HomeAssistant,
    mock_homewizardenergy: MagicMock,
    exception: Exception,
    reason: str,
) -> None:
    """Test check detecting disabled api."""
    mock_homewizardenergy.device.side_effect = exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_IP_ADDRESS: "127.0.0.1"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": reason}
    assert result["data_schema"]({}) == {CONF_IP_ADDRESS: "127.0.0.1"}

    # Recover from error
    mock_homewizardenergy.device.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_IP_ADDRESS: "127.0.0.1"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    ("exception", "reason"),
    [
        (Exception, "unknown_error"),
        (UnsupportedError, "unsupported_api_version"),
    ],
)
async def test_abort_flow(
    hass: HomeAssistant,
    mock_homewizardenergy: MagicMock,
    exception: Exception,
    reason: str,
) -> None:
    """Test check detecting error with api."""
    mock_homewizardenergy.device.side_effect = exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_IP_ADDRESS: "2.2.2.2"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


@pytest.mark.usefixtures("mock_homewizardenergy", "mock_setup_entry")
async def test_reauth_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauth flow while API is enabled."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


async def test_reauth_error(
    hass: HomeAssistant,
    mock_homewizardenergy: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauth flow while API is still disabled."""
    mock_homewizardenergy.device.side_effect = DisabledError
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "api_not_enabled"}


async def test_reconfigure(
    hass: HomeAssistant,
    mock_homewizardenergy: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfiguration."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {}

    # original entry
    assert mock_config_entry.data[CONF_IP_ADDRESS] == "127.0.0.1"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_IP_ADDRESS: "1.0.0.127",
        },
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    # changed entry
    assert mock_config_entry.data[CONF_IP_ADDRESS] == "1.0.0.127"


async def test_reconfigure_nochange(
    hass: HomeAssistant,
    mock_homewizardenergy: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfiguration without changing values."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {}

    # original entry
    assert mock_config_entry.data[CONF_IP_ADDRESS] == "127.0.0.1"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_IP_ADDRESS: "127.0.0.1",
        },
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    # changed entry
    assert mock_config_entry.data[CONF_IP_ADDRESS] == "127.0.0.1"


async def test_reconfigure_wrongdevice(
    hass: HomeAssistant,
    mock_homewizardenergy: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test entering ip of other device and prevent changing it based on serial."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {}

    # simulate different serial number, as if user entered wrong IP
    mock_homewizardenergy.device.return_value.serial = "not_5c2fafabcdef"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_IP_ADDRESS: "1.0.0.127",
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_device"

    # entry should still be original entry
    assert mock_config_entry.data[CONF_IP_ADDRESS] == "127.0.0.1"


@pytest.mark.parametrize(
    ("exception", "reason"),
    [(DisabledError, "api_not_enabled"), (RequestError, "network_error")],
)
async def test_reconfigure_cannot_connect(
    hass: HomeAssistant,
    mock_homewizardenergy: MagicMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    reason: str,
) -> None:
    """Test reconfiguration fails when not able to connect."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {}

    mock_homewizardenergy.device.side_effect = exception
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_IP_ADDRESS: "1.0.0.127",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": reason}
    assert result["data_schema"]({}) == {CONF_IP_ADDRESS: "127.0.0.1"}

    # attempt with valid IP should work
    mock_homewizardenergy.device.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_IP_ADDRESS: "1.0.0.127",
        },
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    # changed entry
    assert mock_config_entry.data[CONF_IP_ADDRESS] == "1.0.0.127"
