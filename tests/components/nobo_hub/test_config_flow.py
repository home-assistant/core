"""Test the Nobø Ecohub config flow."""

from unittest.mock import AsyncMock, PropertyMock, patch

from homeassistant import config_entries
from homeassistant.components.nobo_hub.const import CONF_OVERRIDE_TYPE, DOMAIN
from homeassistant.const import CONF_IP_ADDRESS
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
        "pynobo.nobo.async_discover_hubs",
        return_value=[("1.1.1.1", "123456789")],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "device": "1.1.1.1",
        },
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {}
    assert result2["step_id"] == "selected"

    with (
        patch("pynobo.nobo.async_connect_hub", return_value=True) as mock_connect,
        patch(
            "pynobo.nobo.hub_info",
            new_callable=PropertyMock,
            create=True,
            return_value={"name": "My Nobø Ecohub"},
        ),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                "serial_suffix": "012",
            },
        )
        await hass.async_block_till_done()

        assert result3["type"] is FlowResultType.CREATE_ENTRY
        assert result3["title"] == "My Nobø Ecohub"
        assert result3["data"] == {
            "ip_address": "1.1.1.1",
            "serial": "123456789012",
        }
        mock_connect.assert_awaited_once_with("1.1.1.1", "123456789012")
        mock_setup_entry.assert_awaited_once()


async def test_configure_manual(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test manual configuration when no hubs are discovered."""
    with patch(
        "pynobo.nobo.async_discover_hubs",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {}
        assert result["step_id"] == "manual"

    with (
        patch("pynobo.nobo.async_connect_hub", return_value=True) as mock_connect,
        patch(
            "pynobo.nobo.hub_info",
            new_callable=PropertyMock,
            create=True,
            return_value={"name": "My Nobø Ecohub"},
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "serial": "123456789012",
                "ip_address": "1.1.1.1",
            },
        )
        await hass.async_block_till_done()

        assert result2["type"] is FlowResultType.CREATE_ENTRY
        assert result2["title"] == "My Nobø Ecohub"
        assert result2["data"] == {
            "serial": "123456789012",
            "ip_address": "1.1.1.1",
        }
        mock_connect.assert_awaited_once_with("1.1.1.1", "123456789012")
        mock_setup_entry.assert_awaited_once()


async def test_configure_user_selected_manual(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test configuration when user selects manual."""
    with patch(
        "pynobo.nobo.async_discover_hubs",
        return_value=[("1.1.1.1", "123456789")],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "device": "manual",
        },
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {}
    assert result2["step_id"] == "manual"

    with (
        patch("pynobo.nobo.async_connect_hub", return_value=True) as mock_connect,
        patch(
            "pynobo.nobo.hub_info",
            new_callable=PropertyMock,
            create=True,
            return_value={"name": "My Nobø Ecohub"},
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "serial": "123456789012",
                "ip_address": "1.1.1.1",
            },
        )
        await hass.async_block_till_done()

        assert result2["type"] is FlowResultType.CREATE_ENTRY
        assert result2["title"] == "My Nobø Ecohub"
        assert result2["data"] == {
            "serial": "123456789012",
            "ip_address": "1.1.1.1",
        }
        mock_connect.assert_awaited_once_with("1.1.1.1", "123456789012")
        mock_setup_entry.assert_awaited_once()


async def test_configure_invalid_serial_suffix(hass: HomeAssistant) -> None:
    """Test we handle invalid serial suffix error."""
    with patch(
        "pynobo.nobo.async_discover_hubs",
        return_value=[("1.1.1.1", "123456789")],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "device": "1.1.1.1",
        },
    )
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {"serial_suffix": "ABC"},
    )

    assert result3["type"] is FlowResultType.FORM
    assert result3["errors"] == {"base": "invalid_serial"}


async def test_configure_invalid_serial_undiscovered(hass: HomeAssistant) -> None:
    """Test we handle invalid serial error."""
    with patch(
        "pynobo.nobo.async_discover_hubs",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "manual"}
        )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"ip_address": "1.1.1.1", "serial": "123456789"},
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_serial"}


async def test_configure_invalid_ip_address(hass: HomeAssistant) -> None:
    """Test we handle invalid ip address error."""
    with patch(
        "pynobo.nobo.async_discover_hubs",
        return_value=[("1.1.1.1", "123456789")],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "manual"}
        )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"serial": "123456789012", "ip_address": "ABCD"},
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_ip"}


async def test_configure_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    with patch(
        "pynobo.nobo.async_discover_hubs",
        return_value=[("1.1.1.1", "123456789")],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "device": "1.1.1.1",
        },
    )

    with patch(
        "pynobo.nobo.async_connect_hub",
        return_value=False,
    ) as mock_connect:
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {"serial_suffix": "012"},
        )
        assert result3["type"] is FlowResultType.FORM
        assert result3["errors"] == {"base": "cannot_connect"}
        mock_connect.assert_awaited_once_with("1.1.1.1", "123456789012")


async def test_dhcp_discovery_new_hub(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """A DHCP-discovered hub routes to `selected` for the user to enter the suffix."""
    with patch(
        "pynobo.nobo.async_discover_hubs",
        return_value={("192.168.1.106", "102000100")},
    ) as mock_discover:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=DHCP_DISCOVERY,
        )

    mock_discover.assert_awaited_once_with(ip="192.168.1.106", autodiscover_wait=5.0)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "selected"

    with (
        patch("pynobo.nobo.async_connect_hub", return_value=True) as mock_connect,
        patch(
            "pynobo.nobo.hub_info",
            new_callable=PropertyMock,
            create=True,
            return_value={"name": "My Nobø Ecohub"},
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"serial_suffix": "098"},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["data"] == {
        "serial": "102000100098",
        "ip_address": "192.168.1.106",
    }
    mock_connect.assert_awaited_once_with("192.168.1.106", "102000100098")
    mock_setup_entry.assert_awaited_once()


async def test_dhcp_discovery_updates_existing_ip(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_unload_entry: AsyncMock,
) -> None:
    """DHCP for a hub already configured updates its stored IP and aborts."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="102000100098",
        data={"serial": "102000100098", "ip_address": "1.1.1.1"},
    )
    config_entry.add_to_hass(hass)

    with patch(
        "pynobo.nobo.async_discover_hubs",
        return_value={("192.168.1.106", "102000100")},
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=DHCP_DISCOVERY,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert config_entry.data[CONF_IP_ADDRESS] == "192.168.1.106"


async def test_dhcp_discovery_ignored_and_configured(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_unload_entry: AsyncMock,
) -> None:
    """A configured entry must win the IP refresh even when an ignored entry shares the prefix.

    An ignored discovery's unique_id is the 9-digit prefix; the configured
    entry's unique_id is the full 12-digit serial. Both `startswith` the
    prefix, so iterating over all entries (including ignored) could refresh
    the wrong one. The configured entry must always win.
    """
    ignored_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="102000100",
        source=config_entries.SOURCE_IGNORE,
    )
    ignored_entry.add_to_hass(hass)
    configured_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="102000100098",
        data={"serial": "102000100098", "ip_address": "1.1.1.1"},
    )
    configured_entry.add_to_hass(hass)

    with patch(
        "pynobo.nobo.async_discover_hubs",
        return_value={("192.168.1.106", "102000100")},
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=DHCP_DISCOVERY,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert configured_entry.data[CONF_IP_ADDRESS] == "192.168.1.106"


async def test_dhcp_discovery_no_broadcast(hass: HomeAssistant) -> None:
    """DHCP at an IP that emits no Nobø broadcast aborts cleanly."""
    with patch("pynobo.nobo.async_discover_hubs", return_value=set()):
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
        data={"serial": "123456789012", "ip_address": "1.1.1.1", "auto_discover": True},
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
