"""Test the Nobø Ecohub config flow."""

from unittest.mock import AsyncMock, PropertyMock, patch

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
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

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
        ({"side_effect": ConnectionRefusedError(61, "")}, "cannot_connect_ip"),
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
    followed by a handshake REJECT (serial mismatch) and raises OSError
    on TCP-level failure (wrong IP / hub offline). We surface these as
    cannot_connect ("check serial number") and cannot_connect_ip
    ("check IP address") respectively.
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


async def test_options_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_unload_entry: AsyncMock,
) -> None:
    """Test the options flow."""
    config_entry = MockConfigEntry(
        domain="nobo_hub",
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
