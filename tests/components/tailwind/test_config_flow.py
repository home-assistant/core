"""Configuration flow tests for the Tailwind integration."""
from ipaddress import ip_address
from unittest.mock import MagicMock

from gotailwind import (
    TailwindAuthenticationError,
    TailwindConnectionError,
    TailwindUnsupportedFirmwareVersionError,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import zeroconf
from homeassistant.components.dhcp import DhcpServiceInfo
from homeassistant.components.tailwind.const import DOMAIN
from homeassistant.config_entries import (
    SOURCE_DHCP,
    SOURCE_REAUTH,
    SOURCE_USER,
    SOURCE_ZEROCONF,
)
from homeassistant.const import CONF_HOST, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


@pytest.mark.usefixtures("mock_tailwind")
async def test_user_flow(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the full happy path user flow from start to finish."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "127.0.0.1",
            CONF_TOKEN: "987654",
        },
    )

    assert result2.get("type") == FlowResultType.CREATE_ENTRY
    assert result2 == snapshot


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (TailwindConnectionError, {CONF_HOST: "cannot_connect"}),
        (TailwindAuthenticationError, {CONF_TOKEN: "invalid_auth"}),
        (Exception, {"base": "unknown"}),
    ],
)
async def test_user_flow_errors(
    hass: HomeAssistant,
    mock_tailwind: MagicMock,
    side_effect: Exception,
    expected_error: dict[str, str],
) -> None:
    """Test we show user form on a connection error."""
    mock_tailwind.status.side_effect = side_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_HOST: "127.0.0.1",
            CONF_TOKEN: "987654",
        },
    )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "user"
    assert result.get("errors") == expected_error

    mock_tailwind.status.side_effect = None
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "127.0.0.2",
            CONF_TOKEN: "123456",
        },
    )
    assert result2.get("type") == FlowResultType.CREATE_ENTRY


async def test_user_flow_unsupported_firmware_version(
    hass: HomeAssistant, mock_tailwind: MagicMock
) -> None:
    """Test configuration flow aborts when the firmware version is not supported."""
    mock_tailwind.status.side_effect = TailwindUnsupportedFirmwareVersionError
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_HOST: "127.0.0.1",
            CONF_TOKEN: "987654",
        },
    )

    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "unsupported_firmware"


@pytest.mark.usefixtures("mock_tailwind")
async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test configuration flow aborts when the device is already configured.

    Also, ensures the existing config entry is updated with the new host.
    """
    mock_config_entry.add_to_hass(hass)
    assert mock_config_entry.data[CONF_HOST] == "127.0.0.127"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_HOST: "127.0.0.1",
            CONF_TOKEN: "987654",
        },
    )

    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "already_configured"
    assert mock_config_entry.data[CONF_HOST] == "127.0.0.1"
    assert mock_config_entry.data[CONF_TOKEN] == "987654"


@pytest.mark.usefixtures("mock_tailwind")
async def test_zeroconf_flow(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the zeroconf happy flow from start to finish."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address("127.0.0.1"),
            ip_addresses=[ip_address("127.0.0.1")],
            port=80,
            hostname="tailwind-3ce90e6d2184.local.",
            name="mock_name",
            properties={
                "device_id": "_3c_e9_e_6d_21_84_",
                "product": "iQ3",
                "SW ver": "10.10",
                "vendor": "tailwind",
            },
            type="mock_type",
        ),
    )

    assert result.get("step_id") == "zeroconf_confirm"
    assert result.get("type") == FlowResultType.FORM

    progress = hass.config_entries.flow.async_progress()
    assert len(progress) == 1
    assert progress[0].get("flow_id") == result["flow_id"]

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_TOKEN: "987654"}
    )

    assert result2.get("type") == FlowResultType.CREATE_ENTRY
    assert result2 == snapshot


@pytest.mark.parametrize(
    ("properties", "expected_reason"),
    [
        ({"SW ver": "10.10"}, "no_device_id"),
        ({"device_id": "_3c_e9_e_6d_21_84_", "SW ver": "0.0"}, "unsupported_firmware"),
    ],
)
async def test_zeroconf_flow_abort_incompatible_properties(
    hass: HomeAssistant, properties: dict[str, str], expected_reason: str
) -> None:
    """Test the zeroconf aborts when it advertises incompatible data."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address("127.0.0.1"),
            ip_addresses=[ip_address("127.0.0.1")],
            port=80,
            hostname="tailwind-3ce90e6d2184.local.",
            name="mock_name",
            properties=properties,
            type="mock_type",
        ),
    )

    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == expected_reason


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (TailwindConnectionError, {"base": "cannot_connect"}),
        (TailwindAuthenticationError, {CONF_TOKEN: "invalid_auth"}),
        (Exception, {"base": "unknown"}),
    ],
)
async def test_zeroconf_flow_errors(
    hass: HomeAssistant,
    mock_tailwind: MagicMock,
    side_effect: Exception,
    expected_error: dict[str, str],
) -> None:
    """Test we show form on a error."""
    mock_tailwind.status.side_effect = side_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address("127.0.0.1"),
            ip_addresses=[ip_address("127.0.0.1")],
            port=80,
            hostname="tailwind-3ce90e6d2184.local.",
            name="mock_name",
            properties={
                "device_id": "_3c_e9_e_6d_21_84_",
                "product": "iQ3",
                "SW ver": "10.10",
                "vendor": "tailwind",
            },
            type="mock_type",
        ),
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_TOKEN: "123456",
        },
    )

    assert result2.get("type") == FlowResultType.FORM
    assert result2.get("step_id") == "zeroconf_confirm"
    assert result2.get("errors") == expected_error

    mock_tailwind.status.side_effect = None
    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_TOKEN: "123456",
        },
    )
    assert result3.get("type") == FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_tailwind")
async def test_zeroconf_flow_not_discovered_again(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the zeroconf doesn't re-discover an existing device.

    Also, ensures the existing config entry is updated with the new host.
    """
    mock_config_entry.add_to_hass(hass)
    assert mock_config_entry.data[CONF_HOST] == "127.0.0.127"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address("127.0.0.1"),
            ip_addresses=[ip_address("127.0.0.1")],
            port=80,
            hostname="tailwind-3ce90e6d2184.local.",
            name="mock_name",
            properties={
                "device_id": "_3c_e9_e_6d_21_84_",
                "product": "iQ3",
                "SW ver": "10.10",
                "vendor": "tailwind",
            },
            type="mock_type",
        ),
    )

    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "already_configured"
    assert mock_config_entry.data[CONF_HOST] == "127.0.0.1"


@pytest.mark.usefixtures("mock_tailwind")
async def test_reauth_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the reauthentication configuration flow."""
    mock_config_entry.add_to_hass(hass)
    assert mock_config_entry.data[CONF_TOKEN] == "123456"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_REAUTH,
            "unique_id": mock_config_entry.unique_id,
            "entry_id": mock_config_entry.entry_id,
        },
        data=mock_config_entry.data,
    )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "reauth_confirm"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TOKEN: "987654"},
    )
    await hass.async_block_till_done()

    assert result2.get("type") == FlowResultType.ABORT
    assert result2.get("reason") == "reauth_successful"

    assert mock_config_entry.data[CONF_TOKEN] == "987654"


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (TailwindConnectionError, {"base": "cannot_connect"}),
        (TailwindAuthenticationError, {CONF_TOKEN: "invalid_auth"}),
        (Exception, {"base": "unknown"}),
    ],
)
async def test_reauth_flow_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tailwind: MagicMock,
    side_effect: Exception,
    expected_error: dict[str, str],
) -> None:
    """Test we show form on a error."""
    mock_config_entry.add_to_hass(hass)
    mock_tailwind.status.side_effect = side_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_REAUTH,
            "unique_id": mock_config_entry.unique_id,
            "entry_id": mock_config_entry.entry_id,
        },
        data=mock_config_entry.data,
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_TOKEN: "123456",
        },
    )

    assert result2.get("type") == FlowResultType.FORM
    assert result2.get("step_id") == "reauth_confirm"
    assert result2.get("errors") == expected_error

    mock_tailwind.status.side_effect = None
    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_TOKEN: "123456",
        },
    )

    assert result3.get("type") == FlowResultType.ABORT
    assert result3.get("reason") == "reauth_successful"


async def test_dhcp_discovery_updates_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test DHCP discovery updates config entries."""
    mock_config_entry.add_to_hass(hass)
    assert mock_config_entry.data[CONF_HOST] == "127.0.0.127"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DhcpServiceInfo(
            hostname="tailwind-3ce90e6d2184.local.",
            ip="127.0.0.1",
            macaddress="3c:e9:0e:6d:21:84",
        ),
    )

    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "already_configured"
    assert mock_config_entry.data[CONF_HOST] == "127.0.0.1"


async def test_dhcp_discovery_ignores_unknown(hass: HomeAssistant) -> None:
    """Test DHCP discovery is only used for updates.

    Anything else will just abort the flow.
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DhcpServiceInfo(
            hostname="tailwind-3ce90e6d2184.local.",
            ip="127.0.0.1",
            macaddress="3c:e9:0e:6d:21:84",
        ),
    )

    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "unknown"
