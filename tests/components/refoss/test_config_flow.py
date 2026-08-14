"""Tests for the refoss Integration."""

from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.components.refoss.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_HOSTS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import FakeDiscovery, build_base_device_mock, build_device_mock

from tests.common import MockConfigEntry, get_schema_suggested_value


@patch("homeassistant.components.refoss.config_flow.DISCOVERY_TIMEOUT", 0)
async def test_creating_entry_sets_up(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test setting up refoss."""
    with (
        patch(
            "homeassistant.components.refoss.util.Discovery",
            return_value=FakeDiscovery(),
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

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOSTS: []}
        )

        assert result["type"] is FlowResultType.CREATE_ENTRY

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

        assert result["type"] is FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOSTS: []}
        )
        assert result["type"] is FlowResultType.ABORT

        await hass.async_block_till_done()

        assert len(mock_setup_entry.mock_calls) == 0


@patch("homeassistant.components.refoss.config_flow.DISCOVERY_TIMEOUT", 0)
async def test_creating_entry_with_hosts(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test setting up Refoss using multiple configured hosts."""
    discovery = FakeDiscovery()
    discovery.mock_devices["abc"].inner_ip = "192.0.2.10"
    discovery.mock_devices["def"] = build_device_mock(
        ip="192.0.2.11", mac="aabbcc112244", uuid="def"
    )

    with patch(
        "homeassistant.components.refoss.util.Discovery", return_value=discovery
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOSTS: ["192.0.2.10", "192.0.2.11"]}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_HOSTS: ["192.0.2.10", "192.0.2.11"]}
    assert discovery.last_hosts == ["192.0.2.10", "192.0.2.11"]
    assert len(mock_setup_entry.mock_calls) == 1


@patch("homeassistant.components.refoss.config_flow.DISCOVERY_TIMEOUT", 0)
async def test_creating_entry_with_unreachable_host(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test setting up Refoss using an unreachable host."""
    discovery = FakeDiscovery()
    discovery.mock_devices["abc"].inner_ip = "192.0.2.10"

    with patch(
        "homeassistant.components.refoss.util.Discovery", return_value=discovery
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOSTS: ["192.0.2.10", "192.0.2.20"]}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert discovery.last_hosts == ["192.0.2.10", "192.0.2.20"]
    assert len(mock_setup_entry.mock_calls) == 0


async def test_invalid_host(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test rejecting an invalid host."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOSTS: ["not-an-ip-address"]}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_HOSTS: "invalid_ipv4_address"}
    assert len(mock_setup_entry.mock_calls) == 0


@patch("homeassistant.components.refoss.config_flow.DISCOVERY_TIMEOUT", 0)
async def test_reconfigure_additional_host(hass: HomeAssistant) -> None:
    """Test adding a host to a legacy single-host configuration."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "192.0.2.10"})
    entry.add_to_hass(hass)
    discovery = FakeDiscovery()
    discovery.mock_devices["abc"].inner_ip = "192.0.2.10"
    discovery.mock_devices["def"] = build_device_mock(
        ip="192.0.2.11", mac="aabbcc112244", uuid="def"
    )

    with (
        patch("homeassistant.components.refoss.util.Discovery", return_value=discovery),
        patch.object(hass.config_entries, "async_reload") as mock_reload,
    ):
        result = await entry.start_reconfigure_flow(hass)
        assert get_schema_suggested_value(result["data_schema"].schema, CONF_HOSTS) == [
            "192.0.2.10"
        ]
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOSTS: ["192.0.2.10", "192.0.2.11"]}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == {CONF_HOSTS: ["192.0.2.10", "192.0.2.11"]}
    assert discovery.last_hosts == ["192.0.2.10", "192.0.2.11"]
    mock_reload.assert_awaited_once_with(entry.entry_id)


@patch("homeassistant.components.refoss.config_flow.DISCOVERY_TIMEOUT", 0)
async def test_reconfigure_automatic_discovery(hass: HomeAssistant) -> None:
    """Test changing from a configured host to automatic discovery."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOSTS: ["192.0.2.10", "192.0.2.11"]}
    )
    entry.add_to_hass(hass)
    discovery = FakeDiscovery()

    with (
        patch("homeassistant.components.refoss.util.Discovery", return_value=discovery),
        patch.object(hass.config_entries, "async_reload") as mock_reload,
    ):
        result = await entry.start_reconfigure_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOSTS: []}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == {}
    assert discovery.last_hosts == [None]
    mock_reload.assert_awaited_once_with(entry.entry_id)
