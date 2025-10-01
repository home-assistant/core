"""Test real devices."""

from unittest.mock import Mock

from aioshelly.const import MODEL_2PM_G3, MODEL_BLU_GATEWAY_G3, MODEL_PRO_EM3
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.shelly.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceRegistry
from homeassistant.helpers.entity_registry import EntityRegistry

from . import force_uptime_value, init_integration, snapshot_device_entities

from tests.common import async_load_json_object_fixture


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_shelly_2pm_gen3_no_relay_names(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    entity_registry: EntityRegistry,
    device_registry: DeviceRegistry,
    monkeypatch: pytest.MonkeyPatch,
    snapshot: SnapshotAssertion,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test Shelly 2PM Gen3 without relay names.

    This device has two relays/channels,we should get a main device and two sub
    devices.
    """
    device_fixture = await async_load_json_object_fixture(hass, "2pm_gen3.json", DOMAIN)
    monkeypatch.setattr(mock_rpc_device, "shelly", device_fixture["shelly"])
    monkeypatch.setattr(mock_rpc_device, "status", device_fixture["status"])
    monkeypatch.setattr(mock_rpc_device, "config", device_fixture["config"])

    await force_uptime_value(hass, freezer)

    config_entry = await init_integration(hass, gen=3, model=MODEL_2PM_G3)

    # Relay 0 sub-device
    entity_id = "switch.test_name_switch_0"

    state = hass.states.get(entity_id)
    assert state

    entry = entity_registry.async_get(entity_id)
    assert entry

    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry
    assert device_entry.name == "Test name Switch 0"

    entity_id = "sensor.test_name_switch_0_power"

    state = hass.states.get(entity_id)
    assert state

    entry = entity_registry.async_get(entity_id)
    assert entry

    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry
    assert device_entry.name == "Test name Switch 0"

    # Relay 1 sub-device
    entity_id = "switch.test_name_switch_1"

    state = hass.states.get(entity_id)
    assert state

    entry = entity_registry.async_get(entity_id)
    assert entry

    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry
    assert device_entry.name == "Test name Switch 1"

    entity_id = "sensor.test_name_switch_1_power"

    state = hass.states.get(entity_id)
    assert state

    entry = entity_registry.async_get(entity_id)
    assert entry

    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry
    assert device_entry.name == "Test name Switch 1"

    # Main device
    entity_id = "update.test_name_firmware"

    state = hass.states.get(entity_id)
    assert state

    entry = entity_registry.async_get(entity_id)
    assert entry

    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry
    assert device_entry.name == "Test name"

    await snapshot_device_entities(
        hass, entity_registry, snapshot, config_entry.entry_id
    )


async def test_shelly_2pm_gen3_relay_names(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    entity_registry: EntityRegistry,
    device_registry: DeviceRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test Shelly 2PM Gen3 with relay names.

    This device has two relays/channels,we should get a main device and two sub
    devices.
    """
    device_fixture = await async_load_json_object_fixture(hass, "2pm_gen3.json", DOMAIN)
    device_fixture["config"]["switch:0"]["name"] = "Kitchen light"
    device_fixture["config"]["switch:1"]["name"] = "Living room light"
    monkeypatch.setattr(mock_rpc_device, "shelly", device_fixture["shelly"])
    monkeypatch.setattr(mock_rpc_device, "status", device_fixture["status"])
    monkeypatch.setattr(mock_rpc_device, "config", device_fixture["config"])

    await init_integration(hass, gen=3, model=MODEL_2PM_G3)

    # Relay 0 sub-device
    entity_id = "switch.kitchen_light"

    state = hass.states.get(entity_id)
    assert state

    entry = entity_registry.async_get(entity_id)
    assert entry

    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry
    assert device_entry.name == "Kitchen light"

    entity_id = "sensor.kitchen_light_power"

    state = hass.states.get(entity_id)
    assert state

    entry = entity_registry.async_get(entity_id)
    assert entry

    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry
    assert device_entry.name == "Kitchen light"

    # Relay 1 sub-device
    entity_id = "switch.living_room_light"

    state = hass.states.get(entity_id)
    assert state

    entry = entity_registry.async_get(entity_id)
    assert entry

    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry
    assert device_entry.name == "Living room light"

    entity_id = "sensor.living_room_light_power"

    state = hass.states.get(entity_id)
    assert state

    entry = entity_registry.async_get(entity_id)
    assert entry

    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry
    assert device_entry.name == "Living room light"

    # Main device
    entity_id = "update.test_name_firmware"

    state = hass.states.get(entity_id)
    assert state

    entry = entity_registry.async_get(entity_id)
    assert entry

    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry
    assert device_entry.name == "Test name"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_shelly_2pm_gen3_cover(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    entity_registry: EntityRegistry,
    device_registry: DeviceRegistry,
    monkeypatch: pytest.MonkeyPatch,
    snapshot: SnapshotAssertion,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test Shelly 2PM Gen3 with cover profile.

    With the cover profile we should only get the main device and no subdevices.
    """
    device_fixture = await async_load_json_object_fixture(
        hass, "2pm_gen3_cover.json", DOMAIN
    )
    monkeypatch.setattr(mock_rpc_device, "shelly", device_fixture["shelly"])
    monkeypatch.setattr(mock_rpc_device, "status", device_fixture["status"])
    monkeypatch.setattr(mock_rpc_device, "config", device_fixture["config"])

    await force_uptime_value(hass, freezer)

    config_entry = await init_integration(hass, gen=3, model=MODEL_2PM_G3)

    entity_id = "cover.test_name"

    state = hass.states.get(entity_id)
    assert state

    entry = entity_registry.async_get(entity_id)
    assert entry

    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry
    assert device_entry.name == "Test name"

    entity_id = "sensor.test_name_power"

    state = hass.states.get(entity_id)
    assert state

    entry = entity_registry.async_get(entity_id)
    assert entry

    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry
    assert device_entry.name == "Test name"

    entity_id = "update.test_name_firmware"

    state = hass.states.get(entity_id)
    assert state

    entry = entity_registry.async_get(entity_id)
    assert entry

    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry
    assert device_entry.name == "Test name"

    await snapshot_device_entities(
        hass, entity_registry, snapshot, config_entry.entry_id
    )


async def test_shelly_2pm_gen3_cover_with_name(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    entity_registry: EntityRegistry,
    device_registry: DeviceRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test Shelly 2PM Gen3 with cover profile and the cover name.

    With the cover profile we should only get the main device and no subdevices.
    """
    device_fixture = await async_load_json_object_fixture(
        hass, "2pm_gen3_cover.json", DOMAIN
    )
    device_fixture["config"]["cover:0"]["name"] = "Bedroom blinds"
    monkeypatch.setattr(mock_rpc_device, "shelly", device_fixture["shelly"])
    monkeypatch.setattr(mock_rpc_device, "status", device_fixture["status"])
    monkeypatch.setattr(mock_rpc_device, "config", device_fixture["config"])

    await init_integration(hass, gen=3, model=MODEL_2PM_G3)

    entity_id = "cover.test_name_bedroom_blinds"

    state = hass.states.get(entity_id)
    assert state

    entry = entity_registry.async_get(entity_id)
    assert entry

    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry
    assert device_entry.name == "Test name"

    entity_id = "sensor.test_name_bedroom_blinds_power"

    state = hass.states.get(entity_id)
    assert state

    entry = entity_registry.async_get(entity_id)
    assert entry

    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry
    assert device_entry.name == "Test name"

    entity_id = "update.test_name_firmware"

    state = hass.states.get(entity_id)
    assert state

    entry = entity_registry.async_get(entity_id)
    assert entry

    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry
    assert device_entry.name == "Test name"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_shelly_pro_3em(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    entity_registry: EntityRegistry,
    device_registry: DeviceRegistry,
    monkeypatch: pytest.MonkeyPatch,
    snapshot: SnapshotAssertion,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test Shelly Pro 3EM.

    We should get the main device and three subdevices, one subdevice per one phase.
    """
    device_fixture = await async_load_json_object_fixture(hass, "pro_3em.json", DOMAIN)
    monkeypatch.setattr(mock_rpc_device, "shelly", device_fixture["shelly"])
    monkeypatch.setattr(mock_rpc_device, "status", device_fixture["status"])
    monkeypatch.setattr(mock_rpc_device, "config", device_fixture["config"])

    await force_uptime_value(hass, freezer)

    config_entry = await init_integration(hass, gen=2, model=MODEL_PRO_EM3)

    # Main device
    entity_id = "sensor.test_name_total_active_power"

    state = hass.states.get(entity_id)
    assert state

    entry = entity_registry.async_get(entity_id)
    assert entry

    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry
    assert device_entry.name == "Test name"

    # Phase A sub-device
    entity_id = "sensor.test_name_phase_a_active_power"

    state = hass.states.get(entity_id)
    assert state

    entry = entity_registry.async_get(entity_id)
    assert entry

    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry
    assert device_entry.name == "Test name Phase A"

    # Phase B sub-device
    entity_id = "sensor.test_name_phase_b_active_power"

    state = hass.states.get(entity_id)
    assert state

    entry = entity_registry.async_get(entity_id)
    assert entry

    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry
    assert device_entry.name == "Test name Phase B"

    # Phase C sub-device
    entity_id = "sensor.test_name_phase_c_active_power"

    state = hass.states.get(entity_id)
    assert state

    entry = entity_registry.async_get(entity_id)
    assert entry

    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry
    assert device_entry.name == "Test name Phase C"

    await snapshot_device_entities(
        hass, entity_registry, snapshot, config_entry.entry_id
    )


async def test_shelly_pro_3em_with_emeter_name(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    entity_registry: EntityRegistry,
    device_registry: DeviceRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test Shelly Pro 3EM when the name for Emeter is set.

    We should get the main device and three subdevices, one subdevice per one phase.
    """
    device_fixture = await async_load_json_object_fixture(hass, "pro_3em.json", DOMAIN)
    device_fixture["config"]["em:0"]["name"] = "Emeter name"
    monkeypatch.setattr(mock_rpc_device, "shelly", device_fixture["shelly"])
    monkeypatch.setattr(mock_rpc_device, "status", device_fixture["status"])
    monkeypatch.setattr(mock_rpc_device, "config", device_fixture["config"])

    await init_integration(hass, gen=2, model=MODEL_PRO_EM3)

    # Main device
    entity_id = "sensor.test_name_total_active_power"

    state = hass.states.get(entity_id)
    assert state

    entry = entity_registry.async_get(entity_id)
    assert entry

    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry
    assert device_entry.name == "Test name"

    # Phase A sub-device
    entity_id = "sensor.test_name_phase_a_active_power"

    state = hass.states.get(entity_id)
    assert state

    entry = entity_registry.async_get(entity_id)
    assert entry

    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry
    assert device_entry.name == "Test name Phase A"

    # Phase B sub-device
    entity_id = "sensor.test_name_phase_b_active_power"

    state = hass.states.get(entity_id)
    assert state

    entry = entity_registry.async_get(entity_id)
    assert entry

    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry
    assert device_entry.name == "Test name Phase B"

    # Phase C sub-device
    entity_id = "sensor.test_name_phase_c_active_power"

    state = hass.states.get(entity_id)
    assert state

    entry = entity_registry.async_get(entity_id)
    assert entry

    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry
    assert device_entry.name == "Test name Phase C"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_block_channel_with_name(
    hass: HomeAssistant,
    mock_block_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    entity_registry: EntityRegistry,
    device_registry: DeviceRegistry,
) -> None:
    """Test block channel with name."""
    monkeypatch.setitem(
        mock_block_device.settings["relays"][0], "name", "Kitchen light"
    )

    await init_integration(hass, 1)

    # channel 1 sub-device; num_outputs is 2 so the name of the channel should be used
    entity_id = "switch.kitchen_light"

    state = hass.states.get(entity_id)
    assert state

    entry = entity_registry.async_get(entity_id)
    assert entry

    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry
    assert device_entry.name == "Kitchen light"

    # main device
    entity_id = "update.test_name_firmware"

    state = hass.states.get(entity_id)
    assert state

    entry = entity_registry.async_get(entity_id)
    assert entry

    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry
    assert device_entry.name == "Test name"


async def test_blu_trv_device_info(
    hass: HomeAssistant,
    mock_blu_trv: Mock,
    entity_registry: EntityRegistry,
    device_registry: DeviceRegistry,
) -> None:
    """Test BLU TRV device info."""
    await init_integration(hass, 3, model=MODEL_BLU_GATEWAY_G3)

    entry = entity_registry.async_get("climate.trv_name")
    assert entry

    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry
    assert device_entry.name == "TRV-Name"
    assert device_entry.model_id == "SBTR-001AEU"
    assert device_entry.sw_version == "v1.2.10"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_wall_display_xl(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    entity_registry: EntityRegistry,
    snapshot: SnapshotAssertion,
    monkeypatch: pytest.MonkeyPatch,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test Wall Display XL."""
    device_fixture = await async_load_json_object_fixture(
        hass, "wall_display_xl.json", DOMAIN
    )
    monkeypatch.setattr(mock_rpc_device, "shelly", device_fixture["shelly"])
    monkeypatch.setattr(mock_rpc_device, "status", device_fixture["status"])
    monkeypatch.setattr(mock_rpc_device, "config", device_fixture["config"])

    await force_uptime_value(hass, freezer)

    config_entry = await init_integration(hass, gen=2)

    await snapshot_device_entities(
        hass, entity_registry, snapshot, config_entry.entry_id
    )
