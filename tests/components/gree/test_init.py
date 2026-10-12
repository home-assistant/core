"""Tests for the Gree Integration."""

from unittest.mock import MagicMock, patch

from greeclimate.exceptions import DeviceTimeoutError

from homeassistant.components.gree.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from .common import FakeDiscovery, build_device_mock

from tests.common import MockConfigEntry

_PATCH_BIND = "homeassistant.components.gree.async_create_and_bind_device"


async def test_setup_simple(hass: HomeAssistant) -> None:
    """Test gree integration is setup."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.gree.climate.async_setup_entry",
            return_value=True,
        ) as climate_setup,
        patch(
            "homeassistant.components.gree.switch.async_setup_entry",
            return_value=True,
        ) as switch_setup,
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

        assert len(climate_setup.mock_calls) == 1
        assert len(switch_setup.mock_calls) == 1
        assert entry.state is ConfigEntryState.LOADED

    # No flows started
    assert len(hass.config_entries.flow.async_progress()) == 0


async def test_unload_config_entry(hass: HomeAssistant) -> None:
    """Test that the async_unload_entry works."""
    # As we have currently no configuration, we just to pass the domain here.
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_static_ip(hass: HomeAssistant) -> None:
    """Test gree integration sets up with static IP entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_IP_ADDRESS: "192.168.1.100"},
    )
    entry.add_to_hass(hass)

    mock_device = build_device_mock(ipAddress="192.168.1.100")

    with (
        patch(_PATCH_BIND, return_value=mock_device),
        patch(
            "homeassistant.components.gree.climate.async_setup_entry",
            return_value=True,
        ) as climate_setup,
        patch(
            "homeassistant.components.gree.switch.async_setup_entry",
            return_value=True,
        ) as switch_setup,
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

        assert len(climate_setup.mock_calls) == 1
        assert len(switch_setup.mock_calls) == 1
        assert entry.state is ConfigEntryState.LOADED


async def test_setup_static_ip_bind_failure(hass: HomeAssistant) -> None:
    """Test static IP entry goes to retry state when bind fails."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_IP_ADDRESS: "192.168.1.100"},
    )
    entry.add_to_hass(hass)

    with patch(_PATCH_BIND, side_effect=DeviceTimeoutError()):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_static_ip_unexpected_bind_error(hass: HomeAssistant) -> None:
    """Test static IP entry retries on network errors."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_IP_ADDRESS: "192.168.1.100"},
    )
    entry.add_to_hass(hass)

    with patch(_PATCH_BIND, side_effect=OSError("Network unreachable")):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.SETUP_RETRY


@patch("homeassistant.components.gree.coordinator.DISCOVERY_TIMEOUT", 0)
async def test_setup_static_ip_probes_device(hass: HomeAssistant) -> None:
    """Test static IP entry probes the device address before binding."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="aabbcc112233",
        data={CONF_IP_ADDRESS: "1.1.1.1"},
    )
    entry.add_to_hass(hass)

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert len(entry.runtime_data.coordinators) == 1
    assert entry.runtime_data.coordinators[0].device.device_info.mac == "aabbcc112233"


@patch("homeassistant.components.gree.coordinator.DISCOVERY_TIMEOUT", 0)
async def test_setup_static_ip_device_not_found(hass: HomeAssistant) -> None:
    """Test static IP entry retries when the device does not answer the probe."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="aabbcc112233",
        data={CONF_IP_ADDRESS: "192.168.1.100"},
    )
    entry.add_to_hass(hass)

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


@patch("homeassistant.components.gree.coordinator.DISCOVERY_TIMEOUT", 0)
async def test_discovery_skips_static_ip_device(
    hass: HomeAssistant, discovery: MagicMock
) -> None:
    """Test discovery does not add a device that is configured by IP address."""
    discovery.side_effect = lambda *args: FakeDiscovery()
    static_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="aabbcc112233",
        data={CONF_IP_ADDRESS: "1.1.1.1"},
    )
    static_entry.add_to_hass(hass)
    discovery_entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN)
    discovery_entry.add_to_hass(hass)

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    assert static_entry.state is ConfigEntryState.LOADED
    assert discovery_entry.state is ConfigEntryState.LOADED
    assert len(static_entry.runtime_data.coordinators) == 1
    assert discovery_entry.runtime_data.coordinators == []
    assert len(hass.states.async_entity_ids("climate")) == 1


@patch("homeassistant.components.gree.coordinator.DISCOVERY_TIMEOUT", 0)
async def test_static_ip_entry_takes_over_discovered_device(
    hass: HomeAssistant, discovery: MagicMock, entity_registry: er.EntityRegistry
) -> None:
    """Test a new static IP entry takes the device over from discovery."""
    discovery.side_effect = lambda *args: FakeDiscovery()
    discovery_entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN)
    discovery_entry.add_to_hass(hass)

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    assert len(discovery_entry.runtime_data.coordinators) == 1

    static_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="aabbcc112233",
        data={CONF_IP_ADDRESS: "1.1.1.1"},
    )
    static_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(static_entry.entry_id)
    await hass.async_block_till_done()

    assert discovery_entry.state is ConfigEntryState.LOADED
    assert discovery_entry.runtime_data.coordinators == []
    assert len(static_entry.runtime_data.coordinators) == 1

    entity_ids = hass.states.async_entity_ids("climate")
    assert len(entity_ids) == 1
    entity = entity_registry.async_get(entity_ids[0])
    assert entity is not None
    assert entity.config_entry_id == static_entry.entry_id
