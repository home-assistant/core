"""Tests for the SMLIGHT sensor platform."""

from unittest.mock import MagicMock

from pysmlight import Info, Sensors
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.smlight.const import DOMAIN
from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import setup_integration

from tests.common import (
    MockConfigEntry,
    async_load_json_object_fixture,
    snapshot_platform,
)

pytestmark = [
    pytest.mark.usefixtures(
        "mock_smlight_client",
    )
]


@pytest.fixture
def platforms() -> list[Platform]:
    """Platforms, which should be loaded during the test."""
    return [Platform.SENSOR]


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.freeze_time("2024-07-01 00:00:00+00:00")
async def test_sensors(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the SMLIGHT sensors."""
    entry = await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


async def test_disabled_by_default_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the disabled by default SMLIGHT sensors."""
    await setup_integration(hass, mock_config_entry)

    for sensor in ("core_uptime", "filesystem_usage", "ram_usage", "zigbee_uptime"):
        assert not hass.states.get(f"sensor.mock_title_{sensor}")

        assert (entry := entity_registry.async_get(f"sensor.mock_title_{sensor}"))
        assert entry.disabled
        assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_zigbee_uptime_disconnected(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_smlight_client: MagicMock,
) -> None:
    """Test for uptime when zigbee socket is disconnected.

    In this case zigbee uptime state should be unknown.
    """
    mock_smlight_client.get_sensors.return_value = Sensors(socket_uptime=0)
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.mock_title_zigbee_uptime")
    assert state.state == STATE_UNKNOWN


async def test_zigbee2_temp_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_smlight_client: MagicMock,
) -> None:
    """Test for zb_temp2 if device has second radio."""
    mock_smlight_client.get_sensors.return_value = Sensors(zb_temp2=20.45)
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.mock_title_zigbee_chip_temp_2")
    assert state
    assert state.state == "20.45"


async def test_zigbee_type_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_smlight_client: MagicMock,
) -> None:
    """Test for zigbee type sensor with second radio."""
    mock_smlight_client.get_info.side_effect = None
    mock_smlight_client.get_info.return_value = Info.from_dict(
        await async_load_json_object_fixture(hass, "info-MR1.json", DOMAIN)
    )
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.mock_title_zigbee_type")
    assert state
    assert state.state == "coordinator"

    state = hass.states.get("sensor.mock_title_zigbee_type_2")
    assert state
    assert state.state == "router"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_psram_usage_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_smlight_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test PSRAM usage sensor creation for u-devices."""
    mock_smlight_client.get_info.side_effect = None
    mock_smlight_client.get_info.return_value = Info(
        MAC="AA:BB:CC:DD:EE:FF",
        model="SLZB-MR3U",
        u_device=True,
    )
    mock_smlight_client.get_sensors.return_value = Sensors(psram_usage=156)

    await setup_integration(hass, mock_config_entry)

    entity_id = entity_registry.async_get_entity_id(
        SENSOR_DOMAIN, DOMAIN, "aa:bb:cc:dd:ee:ff_psram_usage"
    )
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "156"
    assert state.attributes["unit_of_measurement"] == "kB"


async def test_psram_usage_sensor_not_created(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_smlight_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test PSRAM usage sensor is not created for non-u devices."""
    mock_smlight_client.get_info.side_effect = None
    mock_smlight_client.get_info.return_value = Info(
        MAC="AA:BB:CC:DD:EE:FF",
        model="SLZB-MR3",
        u_device=False,
    )
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.mock_title_psram_usage") is None

    entity_id = entity_registry.async_get_entity_id(
        SENSOR_DOMAIN, DOMAIN, "aa:bb:cc:dd:ee:ff_psram_usage"
    )
    assert entity_id is None
