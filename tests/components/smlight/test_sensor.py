"""Tests for the SMLIGHT sensor platform."""

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.smlight.const import SMLIGHT_SLZB_REBOOT_EVENT
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry

pytestmark = [
    pytest.mark.usefixtures(
        "setup_platform",
        "mock_smlight_client",
    )
]


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.freeze_time("2024-07-01 00:00:00+00:00")
@pytest.mark.parametrize(
    "entity_id",
    [
        "sensor.slzb_06_core_soc_temp",
        "sensor.slzb_06_zigbee_soc_temp",
        "sensor.slzb_06_ram_usage",
        "sensor.slzb_06_filesystem_usage",
        "sensor.slzb_06_core_uptime",
        "sensor.slzb_06_zigbee_uptime",
    ],
)
async def test_sensors(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    entity_id: str,
) -> None:
    """Test the SMLIGHT sensors."""

    assert (state := hass.states.get(entity_id))
    assert state == snapshot

    assert (entry := entity_registry.async_get(entity_id))
    assert entry == snapshot

    assert entry.device_id
    assert (device_entry := device_registry.async_get(entry.device_id))
    assert device_entry == snapshot


@pytest.mark.parametrize(
    "entity_id",
    [
        "sensor.slzb_06_ram_usage",
        "sensor.slzb_06_filesystem_usage",
        "sensor.slzb_06_core_uptime",
        "sensor.slzb_06_zigbee_uptime",
    ],
)
async def test_disabled_by_default_sensors(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, entity_id: str
) -> None:
    """Test the disabled by default SMLIGHT sensors."""
    assert not hass.states.get(entity_id)

    assert (entry := entity_registry.async_get(entity_id))
    assert entry.disabled
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_zigbee_uptime_disconnected(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test for uptime when zigbee socket is disconnected.

    In this case zigbee uptime state should be unknown.
    """
    coordinator = mock_config_entry.runtime_data
    coordinator.data.sensors.socket_uptime = 0
    await coordinator.async_refresh()

    state = hass.states.get("sensor.slzb_06_zigbee_uptime")
    assert state.state == STATE_UNKNOWN


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_slzb_reboot_event(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test for SLZB reboot event fired on reset uptime."""
    result = []

    async def handle_event(event):
        result.append(event)

    hass.bus.async_listen_once(SMLIGHT_SLZB_REBOOT_EVENT, handle_event)
    coordinator = mock_config_entry.runtime_data
    coordinator.data.sensors.uptime = 15
    await coordinator.async_refresh()

    assert len(result) == 1
    assert result[0].data["device_id"] == "aa:bb:cc:dd:ee:ff"
    assert result[0].data["host"] == "slzb-06"
