"""Tests for the refoss Integration."""

from collections.abc import Generator
from ipaddress import IPv4Address
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.refoss.const import CONF_NETWORKS, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import FakeDiscovery, build_base_device_mock

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def mock_ipv4_broadcasts() -> Generator[AsyncMock]:
    """Return the enabled-adapter broadcasts used by config-flow discovery."""
    with patch(
        "homeassistant.components.refoss.config_flow.async_get_ipv4_broadcast_addresses",
        new_callable=AsyncMock,
        return_value={IPv4Address("255.255.255.255"), IPv4Address("10.9.8.255")},
    ) as mock_broadcasts:
        yield mock_broadcasts


@patch("homeassistant.components.refoss.config_flow.DISCOVERY_TIMEOUT", 0)
async def test_creating_entry_sets_up(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test setting up refoss."""
    discovery = FakeDiscovery()
    with (
        patch(
            "homeassistant.components.refoss.util.Discovery",
            return_value=discovery,
        ),
        patch(
            "homeassistant.components.refoss.bridge.async_build_base_device",
            return_value=build_base_device_mock(),
        ),
        patch(
            "homeassistant.components.refoss.switch.isinstance",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["options"] == {}
        probed = discovery.probes[0]
        assert probed is not None
        assert "255.255.255.255" in probed
        assert "10.9.8.255" in probed
        assert "192.168.20.1" not in probed

        await hass.async_block_till_done()

        assert len(mock_setup_entry.mock_calls) == 1


@patch("homeassistant.components.refoss.config_flow.DISCOVERY_TIMEOUT", 0)
async def test_creating_entry_has_no_devices(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test setting up Refoss no devices."""
    with patch(
        "homeassistant.components.refoss.util.Discovery",
        return_value=FakeDiscovery(),
    ) as discovery:
        discovery.return_value.mock_devices = {}

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        # Confirmation form
        assert result["type"] is FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "no_devices_found"

        await hass.async_block_till_done()

        assert len(mock_setup_entry.mock_calls) == 0


@pytest.mark.parametrize(
    "networks",
    [
        "10.0.0.0/16",
        "10.1.2.3/32",
        "10.1.2.0/25",
        "not-an-ip",
        "2001:db8::1",
        "10.0.0.0/24,10.0.1.0/24,10.0.2.0/24,10.0.3.0/24,10.0.4.0/24",
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
@patch("homeassistant.components.refoss.config_flow.DISCOVERY_TIMEOUT", 0)
async def test_user_flow_rejects_invalid_networks(
    hass: HomeAssistant, networks: str
) -> None:
    """Test invalid networks are rejected, then a valid address creates an entry."""
    discovery = FakeDiscovery()
    with patch(
        "homeassistant.components.refoss.util.Discovery",
        return_value=discovery,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_NETWORKS: networks}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {CONF_NETWORKS: "invalid_networks"}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_NETWORKS: "10.1.2.17"}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"] == {CONF_NETWORKS: ["10.1.2.17"]}


@patch("homeassistant.components.refoss.config_flow.DISCOVERY_TIMEOUT", 0)
async def test_user_flow_stores_subnet(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test a VLAN subnet is probed and stored."""
    discovery = FakeDiscovery()
    with patch(
        "homeassistant.components.refoss.util.Discovery",
        return_value=discovery,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_NETWORKS: "192.168.20.5/24"}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"] == {CONF_NETWORKS: ["192.168.20.0/24"]}
    probed = discovery.probes[0]
    assert probed is not None
    assert "255.255.255.255" in probed
    assert "192.168.20.255" in probed
    assert "192.168.20.1" in probed
    assert "192.168.20.254" in probed
    assert "192.168.20.0" not in probed
    assert len(mock_setup_entry.mock_calls) == 1


async def test_options_flow_updates_networks(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test the options flow replaces configured networks."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_NETWORKS: "192.168.8.0/24, 10.1.2.3"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.options == {CONF_NETWORKS: ["10.1.2.3", "192.168.8.0/24"]}
    assert len(mock_setup_entry.mock_calls) == 0


@pytest.mark.usefixtures("mock_setup_entry")
async def test_options_flow_rejects_invalid_networks(
    hass: HomeAssistant,
) -> None:
    """Test the options flow rejects a subnet larger than /24, then accepts a /24."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_NETWORKS: "10.0.0.0/8"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_NETWORKS: "invalid_networks"}
    assert CONF_NETWORKS not in entry.options

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_NETWORKS: "192.168.8.0/24"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.options == {CONF_NETWORKS: ["192.168.8.0/24"]}


@patch("homeassistant.components.refoss.config_flow.DISCOVERY_TIMEOUT", 0)
async def test_user_flow_accepts_chinese_commas(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test Chinese commas separate multiple networks."""
    discovery = FakeDiscovery()
    with patch(
        "homeassistant.components.refoss.util.Discovery",
        return_value=discovery,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_NETWORKS: "192.168.20.0/24，10.1.2.3"}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"] == {CONF_NETWORKS: ["10.1.2.3", "192.168.20.0/24"]}
    probed = discovery.probes[0]
    assert probed is not None
    assert "10.1.2.3" in probed
    assert "10.1.2.1" not in probed
    assert "192.168.20.1" in probed
    assert len(mock_setup_entry.mock_calls) == 1


@patch("homeassistant.components.refoss.config_flow.DISCOVERY_TIMEOUT", 0)
async def test_user_flow_probes_exact_host(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test a configured IPv4 address is probed without expanding to its /24."""
    discovery = FakeDiscovery()
    with patch(
        "homeassistant.components.refoss.util.Discovery",
        return_value=discovery,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_NETWORKS: "10.1.2.17"}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"] == {CONF_NETWORKS: ["10.1.2.17"]}
    probed = discovery.probes[0]
    assert probed is not None
    assert "10.1.2.17" in probed
    assert "10.1.2.1" not in probed
    assert "10.1.2.255" not in probed
    assert len(mock_setup_entry.mock_calls) == 1
