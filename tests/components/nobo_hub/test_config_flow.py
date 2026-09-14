"""Test the Nobø Ecohub config flow."""

from unittest.mock import AsyncMock, PropertyMock, patch

from pynobo import PynoboConnectionError
import pytest

from homeassistant import config_entries
from homeassistant.components.nobo_hub.const import (
    CONF_OVERRIDE_TYPE,
    CONF_SERIAL,
    DOMAIN,
)
from homeassistant.const import CONF_IP_ADDRESS, CONF_MAC
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .conftest import SERIAL, STORED_IP

from tests.common import MockConfigEntry

DHCP_DISCOVERY = DhcpServiceInfo(
    ip="192.168.1.106",
    macaddress="7c830602644f",
    hostname="hubdo",
)


async def test_configure_with_discover(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test configure with discover."""
    with patch(
        "homeassistant.components.nobo_hub.config_flow.nobo.async_discover_hubs",
        return_value=[("1.1.1.1", "123456789")],
    ) as mock_discover:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
    mock_discover.assert_awaited_once_with(autodiscover_wait=5.0)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"device": "1.1.1.1"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}
    assert result["step_id"] == "selected"

    with (
        patch(
            "homeassistant.components.nobo_hub.config_flow.nobo.async_connect_hub",
            return_value=True,
        ) as mock_connect,
        patch(
            "homeassistant.components.nobo_hub.config_flow.nobo.hub_info",
            new_callable=PropertyMock,
            create=True,
            return_value={"name": "My Nobø Ecohub"},
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"serial_suffix": "012"},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "My Nobø Ecohub"
    assert result["result"].unique_id == "123456789012"
    assert result["data"] == {
        CONF_IP_ADDRESS: "1.1.1.1",
        CONF_SERIAL: "123456789012",
        CONF_MAC: None,
    }
    mock_connect.assert_awaited_once_with("1.1.1.1", "123456789012")
    mock_setup_entry.assert_awaited_once()


@pytest.mark.parametrize(
    ("discovered", "expected_devices", "selected_device"),
    [
        # Same IP+prefix hidden; sibling with same prefix at a different IP shown.
        (
            [("1.1.1.1", "111111111"), ("2.2.2.2", "111111111")],
            {"2.2.2.2", "manual"},
            "2.2.2.2",
        ),
        # Same IP, different prefix → different hub (e.g. replacement), shown.
        ([("1.1.1.1", "222222222")], {"1.1.1.1", "manual"}, "1.1.1.1"),
    ],
    ids=["sibling_different_ip", "replaced_hub"],
)
async def test_configure_filters_configured_hubs(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    discovered: list[tuple[str, str]],
    expected_devices: set[str],
    selected_device: str,
) -> None:
    """Configured (IP, prefix) pairs are hidden; the user can pick a remaining one."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id="111111111012",
        data={CONF_SERIAL: "111111111012", CONF_IP_ADDRESS: "1.1.1.1"},
    ).add_to_hass(hass)

    with patch("pynobo.nobo.async_discover_hubs", return_value=discovered):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert set(result["data_schema"].schema["device"].container) == expected_devices

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"device": selected_device},
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "selected"

    with (
        patch("pynobo.nobo.async_connect_hub", return_value=True),
        patch(
            "pynobo.nobo.hub_info",
            new_callable=PropertyMock,
            create=True,
            return_value={"name": "My Nobø Ecohub"},
        ),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {"serial_suffix": "999"},
        )

    assert result3["type"] is FlowResultType.CREATE_ENTRY


async def test_configure_skips_user_step_when_all_configured(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Flow falls through to manual when every discovered hub matches a configured pair."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id="111111111012",
        data={CONF_SERIAL: "111111111012", CONF_IP_ADDRESS: "1.1.1.1"},
    ).add_to_hass(hass)

    with patch(
        "pynobo.nobo.async_discover_hubs",
        return_value=[("1.1.1.1", "111111111")],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"

    with (
        patch("pynobo.nobo.async_connect_hub", return_value=True),
        patch(
            "pynobo.nobo.hub_info",
            new_callable=PropertyMock,
            create=True,
            return_value={"name": "My Nobø Ecohub"},
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"serial": "999999999999", "ip_address": "9.9.9.9"},
        )

    assert result2["type"] is FlowResultType.CREATE_ENTRY


async def test_configure_manual(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test manual configuration when no hubs are discovered."""
    with patch(
        "homeassistant.components.nobo_hub.config_flow.nobo.async_discover_hubs",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {}
        assert result["step_id"] == "manual"

    with (
        patch(
            "homeassistant.components.nobo_hub.config_flow.nobo.async_connect_hub",
            return_value=True,
        ) as mock_connect,
        patch(
            "homeassistant.components.nobo_hub.config_flow.nobo.hub_info",
            new_callable=PropertyMock,
            create=True,
            return_value={"name": "My Nobø Ecohub"},
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_SERIAL: "123456789012",
                CONF_IP_ADDRESS: "1.1.1.1",
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "My Nobø Ecohub"
    assert result["result"].unique_id == "123456789012"
    assert result["data"] == {
        CONF_SERIAL: "123456789012",
        CONF_IP_ADDRESS: "1.1.1.1",
        CONF_MAC: None,
    }
    mock_connect.assert_awaited_once_with("1.1.1.1", "123456789012")
    mock_setup_entry.assert_awaited_once()


async def test_configure_user_selected_manual(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test configuration when user selects manual."""
    with patch(
        "homeassistant.components.nobo_hub.config_flow.nobo.async_discover_hubs",
        return_value=[("1.1.1.1", "123456789")],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"device": "manual"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}
    assert result["step_id"] == "manual"

    with (
        patch(
            "homeassistant.components.nobo_hub.config_flow.nobo.async_connect_hub",
            return_value=True,
        ) as mock_connect,
        patch(
            "homeassistant.components.nobo_hub.config_flow.nobo.hub_info",
            new_callable=PropertyMock,
            create=True,
            return_value={"name": "My Nobø Ecohub"},
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_SERIAL: "123456789012",
                CONF_IP_ADDRESS: "1.1.1.1",
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "My Nobø Ecohub"
    assert result["result"].unique_id == "123456789012"
    assert result["data"] == {
        CONF_SERIAL: "123456789012",
        CONF_IP_ADDRESS: "1.1.1.1",
        CONF_MAC: None,
    }
    mock_connect.assert_awaited_once_with("1.1.1.1", "123456789012")
    mock_setup_entry.assert_awaited_once()


async def test_configure_invalid_serial_suffix(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Invalid serial suffix surfaces an error; valid suffix recovers."""
    with patch(
        "homeassistant.components.nobo_hub.config_flow.nobo.async_discover_hubs",
        return_value=[("1.1.1.1", "123456789")],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"device": "1.1.1.1"},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"serial_suffix": "ABC"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_serial"}

    with (
        patch(
            "homeassistant.components.nobo_hub.config_flow.nobo.async_connect_hub",
            return_value=True,
        ),
        patch(
            "homeassistant.components.nobo_hub.config_flow.nobo.hub_info",
            new_callable=PropertyMock,
            create=True,
            return_value={"name": "My Nobø Ecohub"},
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"serial_suffix": "012"},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    mock_setup_entry.assert_awaited_once()


async def test_configure_invalid_serial_undiscovered(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Invalid serial in the manual step surfaces an error; valid serial recovers."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "manual"}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_IP_ADDRESS: "1.1.1.1", CONF_SERIAL: "123456789"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_serial"}

    with (
        patch(
            "homeassistant.components.nobo_hub.config_flow.nobo.async_connect_hub",
            return_value=True,
        ),
        patch(
            "homeassistant.components.nobo_hub.config_flow.nobo.hub_info",
            new_callable=PropertyMock,
            create=True,
            return_value={"name": "My Nobø Ecohub"},
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_IP_ADDRESS: "1.1.1.1", CONF_SERIAL: "123456789012"},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    mock_setup_entry.assert_awaited_once()


async def test_configure_invalid_ip_address(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Invalid IP surfaces an error; valid IP recovers."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "manual"}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_SERIAL: "123456789012", CONF_IP_ADDRESS: "ABCD"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_ip"}

    with (
        patch(
            "homeassistant.components.nobo_hub.config_flow.nobo.async_connect_hub",
            return_value=True,
        ),
        patch(
            "homeassistant.components.nobo_hub.config_flow.nobo.hub_info",
            new_callable=PropertyMock,
            create=True,
            return_value={"name": "My Nobø Ecohub"},
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_SERIAL: "123456789012", CONF_IP_ADDRESS: "1.1.1.1"},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    mock_setup_entry.assert_awaited_once()


@pytest.mark.parametrize(
    ("connect_outcome", "expected_error"),
    [
        ({"return_value": False}, "cannot_connect"),
        (
            {"side_effect": PynoboConnectionError("Failed to connect")},
            "cannot_connect_ip",
        ),
    ],
    ids=["serial_mismatch", "tcp_failure"],
)
async def test_configure_cannot_connect(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    connect_outcome: dict[str, object],
    expected_error: str,
) -> None:
    """Connect failures map to distinct error keys; retry recovers.

    pynobo's async_connect_hub returns False on a successful TCP connect
    followed by a handshake REJECT (serial mismatch) and raises
    PynoboConnectionError on TCP-level failure (wrong IP / hub offline).
    We surface these as cannot_connect ("check serial number") and
    cannot_connect_ip ("check IP address") respectively.
    """
    with patch(
        "homeassistant.components.nobo_hub.config_flow.nobo.async_discover_hubs",
        return_value=[("1.1.1.1", "123456789")],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"device": "1.1.1.1"},
    )

    with patch(
        "homeassistant.components.nobo_hub.config_flow.nobo.async_connect_hub",
        **connect_outcome,
    ) as mock_connect:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"serial_suffix": "012"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}
    mock_connect.assert_awaited_once_with("1.1.1.1", "123456789012")

    with (
        patch(
            "homeassistant.components.nobo_hub.config_flow.nobo.async_connect_hub",
            return_value=True,
        ),
        patch(
            "homeassistant.components.nobo_hub.config_flow.nobo.hub_info",
            new_callable=PropertyMock,
            create=True,
            return_value={"name": "My Nobø Ecohub"},
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"serial_suffix": "012"},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    mock_setup_entry.assert_awaited_once()


async def test_dhcp_discovery_new_hub(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """A DHCP-discovered hub routes to `selected` for the user to enter the suffix."""
    with patch(
        "homeassistant.components.nobo_hub.config_flow.nobo.async_discover_hubs",
        return_value={("192.168.1.106", "102000100")},
    ) as mock_discover:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=DHCP_DISCOVERY,
        )

    mock_discover.assert_awaited_once_with(ip="192.168.1.106", autodiscover_wait=15.0)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "selected"

    with (
        patch(
            "homeassistant.components.nobo_hub.config_flow.nobo.async_connect_hub",
            return_value=True,
        ) as mock_connect,
        patch(
            "homeassistant.components.nobo_hub.config_flow.nobo.hub_info",
            new_callable=PropertyMock,
            create=True,
            return_value={"name": "My Nobø Ecohub"},
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"serial_suffix": "098"},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "My Nobø Ecohub"
    assert result["result"].unique_id == "102000100098"
    assert result["data"] == {
        CONF_SERIAL: "102000100098",
        CONF_IP_ADDRESS: "192.168.1.106",
        CONF_MAC: "7c830602644f",
    }
    mock_connect.assert_awaited_once_with("192.168.1.106", "102000100098")
    mock_setup_entry.assert_awaited_once()


async def test_dhcp_discovery_backfill_aborts_when_ip_matches(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_unload_entry: AsyncMock,
) -> None:
    """Matching IP + prefix backfills the MAC and aborts as already_configured."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="102000100098",
        data={
            CONF_SERIAL: "102000100098",
            CONF_IP_ADDRESS: "192.168.1.106",
            CONF_MAC: None,
        },
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.nobo_hub.config_flow.nobo.async_discover_hubs",
        return_value={("192.168.1.106", "102000100")},
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=DHCP_DISCOVERY,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert config_entry.data[CONF_IP_ADDRESS] == "192.168.1.106"
    assert config_entry.data[CONF_MAC] == "7c830602644f"


async def test_dhcp_discovery_backfill_proceeds_when_ip_mismatched(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_unload_entry: AsyncMock,
) -> None:
    """Mismatched IP (sibling hub from same production batch) doesn't clobber an existing entry's MAC.

    Two hubs from the same production batch share the 9-digit serial
    prefix but have different IPs. Requiring IP match prevents a DHCP
    packet from one hub clobbering a sibling entry's MAC. The flow falls
    through to the `selected` step so the user can configure the new hub.
    """
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="102000100098",
        data={
            CONF_SERIAL: "102000100098",
            CONF_IP_ADDRESS: "192.168.1.100",
            CONF_MAC: None,
        },
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.nobo_hub.config_flow.nobo.async_discover_hubs",
        return_value={("192.168.1.106", "102000100")},
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=DHCP_DISCOVERY,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "selected"
    assert config_entry.data[CONF_IP_ADDRESS] == "192.168.1.100"
    assert config_entry.data[CONF_MAC] is None

    with (
        patch(
            "homeassistant.components.nobo_hub.config_flow.nobo.async_connect_hub",
            return_value=True,
        ),
        patch(
            "homeassistant.components.nobo_hub.config_flow.nobo.hub_info",
            new_callable=PropertyMock,
            create=True,
            return_value={"name": "My Nobø Ecohub"},
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"serial_suffix": "099"},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "102000100099"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_dhcp_discovery_skips_broadcast_when_mac_known(
    hass: HomeAssistant, mock_unload_entry: AsyncMock
) -> None:
    """A configured entry with a stored MAC refreshes its IP without broadcasting."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="102000100098",
        data={
            CONF_SERIAL: "102000100098",
            CONF_IP_ADDRESS: "1.1.1.1",
            CONF_MAC: "7c830602644f",
        },
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.nobo_hub.config_flow.nobo.async_discover_hubs",
    ) as mock_discover:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=DHCP_DISCOVERY,
        )

    mock_discover.assert_not_awaited()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert config_entry.data[CONF_IP_ADDRESS] == "192.168.1.106"
    assert config_entry.data[CONF_MAC] == "7c830602644f"


async def test_dhcp_discovery_aborts_when_ignored_mac_matches(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Rediscovery of a previously-ignored hub aborts on matching MAC."""
    ignored_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="7c:83:06:02:64:4f",
        source=config_entries.SOURCE_IGNORE,
    )
    ignored_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=DHCP_DISCOVERY,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_dhcp_discovery_proceeds_when_ignored_mac_differs(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """A sibling hub (different MAC, same serial prefix) is not shadowed by an ignored entry.

    The 9-digit serial prefix would match, but using the MAC as the
    discovery flow's unique_id prevents the false-shadowing.
    """
    ignored_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="7c:83:06:99:99:99",
        source=config_entries.SOURCE_IGNORE,
    )
    ignored_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.nobo_hub.config_flow.nobo.async_discover_hubs",
        return_value={("192.168.1.106", "102000100")},
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=DHCP_DISCOVERY,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "selected"

    with (
        patch(
            "homeassistant.components.nobo_hub.config_flow.nobo.async_connect_hub",
            return_value=True,
        ),
        patch(
            "homeassistant.components.nobo_hub.config_flow.nobo.hub_info",
            new_callable=PropertyMock,
            create=True,
            return_value={"name": "My Nobø Ecohub"},
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"serial_suffix": "098"},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "102000100098"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_dhcp_discovery_configured_wins_over_ignored_mac(
    hass: HomeAssistant, mock_unload_entry: AsyncMock
) -> None:
    """A configured entry's IP refresh wins over an ignored entry with the same MAC.

    If both an ignored entry (unique_id = formatted MAC) and a configured
    entry (with the MAC stored in data) exist for the same hub, the
    configured entry's fast-path IP refresh fires before the ignored MAC
    can abort the flow. Otherwise the ignored entry would silently block
    every future DHCP-driven IP update for the active configuration.
    """
    ignored_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="7c:83:06:02:64:4f",
        source=config_entries.SOURCE_IGNORE,
    )
    ignored_entry.add_to_hass(hass)
    configured_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="102000100098",
        data={
            CONF_SERIAL: "102000100098",
            CONF_IP_ADDRESS: "1.1.1.1",
            CONF_MAC: "7c830602644f",
        },
    )
    configured_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.nobo_hub.config_flow.nobo.async_discover_hubs",
    ) as mock_discover:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=DHCP_DISCOVERY,
        )

    mock_discover.assert_not_awaited()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert configured_entry.data[CONF_IP_ADDRESS] == "192.168.1.106"


async def test_dhcp_discovery_no_broadcast(hass: HomeAssistant) -> None:
    """DHCP at an IP that emits no Nobø broadcast aborts cleanly."""
    with patch(
        "homeassistant.components.nobo_hub.config_flow.nobo.async_discover_hubs",
        return_value=set(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=DHCP_DISCOVERY,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_discover"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_flow_changes_ip(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A new IP is probed before save when the entry is not loaded."""
    new_ip = "192.168.1.200"
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["description_placeholders"] == {CONF_SERIAL: SERIAL}

    with (
        patch(
            "homeassistant.components.nobo_hub.config_flow.nobo.async_connect_hub",
            return_value=True,
        ) as mock_connect,
        patch(
            "homeassistant.components.nobo_hub.config_flow.nobo.hub_info",
            new_callable=PropertyMock,
            create=True,
            return_value={"name": "My Nobø Ecohub"},
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_IP_ADDRESS: new_ip},
        )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == {CONF_SERIAL: SERIAL, CONF_IP_ADDRESS: new_ip}
    mock_connect.assert_awaited_once_with(new_ip, SERIAL)


@pytest.mark.parametrize(
    ("submitted_ip", "connect_outcome", "expected_error", "expected_connect_count"),
    [
        (
            "192.168.1.200",
            {"side_effect": PynoboConnectionError("Failed to connect")},
            "cannot_connect_ip",
            1,
        ),
        ("not-an-ip", {"return_value": True}, "invalid_ip", 0),
    ],
    ids=["unreachable_ip", "invalid_format"],
)
@pytest.mark.usefixtures("mock_setup_entry", "mock_unload_entry")
async def test_reconfigure_flow_rejects_bad_ip(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    submitted_ip: str,
    connect_outcome: dict[str, object],
    expected_error: str,
    expected_connect_count: int,
) -> None:
    """A bad IP is rejected inline; resubmitting a good IP completes the reconfigure."""
    recovery_ip = "192.168.1.201"
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    with patch(
        "homeassistant.components.nobo_hub.config_flow.nobo.async_connect_hub",
        **connect_outcome,
    ) as mock_connect:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_IP_ADDRESS: submitted_ip},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {CONF_IP_ADDRESS: expected_error}
    assert mock_config_entry.data[CONF_IP_ADDRESS] == STORED_IP
    assert mock_connect.await_count == expected_connect_count

    with (
        patch(
            "homeassistant.components.nobo_hub.config_flow.nobo.async_connect_hub",
            return_value=True,
        ),
        patch(
            "homeassistant.components.nobo_hub.config_flow.nobo.hub_info",
            new_callable=PropertyMock,
            create=True,
            return_value={"name": "My Nobø Ecohub"},
        ),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {CONF_IP_ADDRESS: recovery_ip},
        )

    assert result3["type"] is FlowResultType.ABORT
    assert result3["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == {CONF_SERIAL: SERIAL, CONF_IP_ADDRESS: recovery_ip}


async def test_reconfigure_flow_unchanged_ip_skips_reload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
    mock_unload_entry: AsyncMock,
) -> None:
    """Submitting the same IP while connected aborts without triggering a reload."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    mock_setup_entry.reset_mock()

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_IP_ADDRESS: STORED_IP},
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reconfigure_successful"
    mock_unload_entry.assert_not_awaited()
    mock_setup_entry.assert_not_awaited()


async def test_reconfigure_flow_changed_ip_triggers_reload_and_skips_probe(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
    mock_unload_entry: AsyncMock,
) -> None:
    """Submitting a different IP while connected reloads the entry without probing."""
    new_ip = "192.168.1.200"
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    mock_setup_entry.reset_mock()
    mock_unload_entry.reset_mock()

    result = await mock_config_entry.start_reconfigure_flow(hass)
    with patch(
        "homeassistant.components.nobo_hub.config_flow.nobo.async_connect_hub"
    ) as mock_connect:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_IP_ADDRESS: new_ip},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_IP_ADDRESS] == new_ip
    mock_connect.assert_not_awaited()
    mock_unload_entry.assert_awaited_once()
    mock_setup_entry.assert_awaited_once()


async def test_options_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_unload_entry: AsyncMock,
) -> None:
    """Test the options flow."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="123456789012",
        data={
            CONF_SERIAL: "123456789012",
            CONF_IP_ADDRESS: "1.1.1.1",
            "auto_discover": True,
        },
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    mock_setup_entry.reset_mock()
    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_OVERRIDE_TYPE: "constant",
        },
    )
    await hass.async_block_till_done()

    assert mock_unload_entry.await_count == 1
    assert mock_setup_entry.await_count == 1
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {CONF_OVERRIDE_TYPE: "constant"}
    mock_unload_entry.reset_mock()
    mock_setup_entry.reset_mock()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_OVERRIDE_TYPE: "now",
        },
    )
    await hass.async_block_till_done()

    assert mock_unload_entry.await_count == 1
    assert mock_setup_entry.await_count == 1
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {CONF_OVERRIDE_TYPE: "now"}
