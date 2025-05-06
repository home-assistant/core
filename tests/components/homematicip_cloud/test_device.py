"""Common tests for HomematicIP devices."""

from unittest.mock import patch

from homematicip.base.enums import EventType

from homeassistant.components.homematicip_cloud import DOMAIN as HMIPC_DOMAIN
from homeassistant.components.homematicip_cloud.hap import HomematicipHAP
from homeassistant.const import STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .helper import (
    HAPID,
    HomeFactory,
    async_manipulate_test_data,
    get_and_check_entity_basics,
)

from tests.common import MockConfigEntry


async def test_hmip_load_all_supported_devices(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory
) -> None:
    """Ensure that all supported devices could be loaded."""
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=None, test_groups=None
    )

    assert len(mock_hap.hmip_device_by_entity_id) == 331


async def test_hmip_remove_device(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    default_mock_hap_factory: HomeFactory,
) -> None:
    """Test Remove of hmip device."""
    entity_id = "light.treppe_ch"
    entity_name = "Treppe CH"
    device_model = "HmIP-BSL"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=["Treppe"]
    )

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )

    assert ha_state.state == STATE_ON
    assert hmip_device

    pre_device_count = len(device_registry.devices)
    pre_entity_count = len(entity_registry.entities)
    pre_mapping_count = len(mock_hap.hmip_device_by_entity_id)

    hmip_device.fire_remove_event()

    await hass.async_block_till_done()

    assert len(device_registry.devices) == pre_device_count - 1
    assert len(entity_registry.entities) == pre_entity_count - 3
    assert len(mock_hap.hmip_device_by_entity_id) == pre_mapping_count - 3


async def test_hmip_add_device(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    default_mock_hap_factory: HomeFactory,
    hmip_config_entry: MockConfigEntry,
) -> None:
    """Test Remove of hmip device."""
    entity_id = "light.treppe_ch"
    entity_name = "Treppe CH"
    device_model = "HmIP-BSL"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=["Treppe"]
    )

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )

    assert ha_state.state == STATE_ON
    assert hmip_device

    pre_device_count = len(device_registry.devices)
    pre_entity_count = len(entity_registry.entities)
    pre_mapping_count = len(mock_hap.hmip_device_by_entity_id)

    hmip_device.fire_remove_event()
    await hass.async_block_till_done()

    assert len(device_registry.devices) == pre_device_count - 1
    assert len(entity_registry.entities) == pre_entity_count - 3
    assert len(mock_hap.hmip_device_by_entity_id) == pre_mapping_count - 3

    reloaded_hap = HomematicipHAP(hass, hmip_config_entry)
    with (
        patch(
            "homeassistant.components.homematicip_cloud.HomematicipHAP",
            return_value=reloaded_hap,
        ),
        patch.object(reloaded_hap, "async_connect"),
        patch.object(reloaded_hap, "get_hap", return_value=mock_hap.home),
        patch(
            "homeassistant.components.homematicip_cloud.hap.asyncio.sleep",
        ),
    ):
        mock_hap.home.fire_create_event(event_type=EventType.DEVICE_ADDED)
        await hass.async_block_till_done()

    assert len(device_registry.devices) == pre_device_count
    assert len(entity_registry.entities) == pre_entity_count
    new_hap = hass.data[HMIPC_DOMAIN][HAPID]
    assert len(new_hap.hmip_device_by_entity_id) == pre_mapping_count


async def test_hmip_remove_group(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    default_mock_hap_factory: HomeFactory,
) -> None:
    """Test Remove of hmip group."""
    entity_id = "switch.strom_group"
    entity_name = "Strom Group"
    device_model = None
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(test_groups=["Strom"])

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )

    assert ha_state.state == STATE_ON
    assert hmip_device

    pre_device_count = len(device_registry.devices)
    pre_entity_count = len(entity_registry.entities)
    pre_mapping_count = len(mock_hap.hmip_device_by_entity_id)

    hmip_device.fire_remove_event()
    await hass.async_block_till_done()

    assert len(device_registry.devices) == pre_device_count
    assert len(entity_registry.entities) == pre_entity_count - 1
    assert len(mock_hap.hmip_device_by_entity_id) == pre_mapping_count - 1


async def test_all_devices_unavailable_when_hap_not_connected(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory
) -> None:
    """Test make all devices unavaulable when hap is not connected."""
    entity_id = "light.treppe_ch"
    entity_name = "Treppe CH"
    device_model = "HmIP-BSL"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=["Treppe"]
    )

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )

    assert ha_state.state == STATE_ON
    assert hmip_device

    assert mock_hap.home.connected

    await async_manipulate_test_data(hass, mock_hap.home, "connected", False)

    ha_state = hass.states.get(entity_id)
    assert ha_state.state == STATE_UNAVAILABLE


async def test_hap_reconnected(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory
) -> None:
    """Test reconnect hap."""
    entity_id = "light.treppe_ch"
    entity_name = "Treppe CH"
    device_model = "HmIP-BSL"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=["Treppe"]
    )

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )

    assert ha_state.state == STATE_ON
    assert hmip_device

    assert mock_hap.home.connected

    await async_manipulate_test_data(hass, mock_hap.home, "connected", False)

    ha_state = hass.states.get(entity_id)
    assert ha_state.state == STATE_UNAVAILABLE

    mock_hap._accesspoint_connected = False
    await async_manipulate_test_data(hass, mock_hap.home, "connected", True)
    await hass.async_block_till_done()
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == STATE_ON


async def test_hap_with_name(
    hass: HomeAssistant, mock_connection, hmip_config_entry: MockConfigEntry
) -> None:
    """Test hap with name."""
    home_name = "TestName"
    entity_id = f"light.{home_name.lower()}_treppe_ch"
    entity_name = f"{home_name} Treppe CH"
    device_model = "HmIP-BSL"

    hmip_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        hmip_config_entry, data={**hmip_config_entry.data, "name": home_name}
    )
    mock_hap = await HomeFactory(
        hass, mock_connection, hmip_config_entry
    ).async_get_mock_hap(test_devices=["Treppe"])
    assert mock_hap

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )

    assert hmip_device
    assert ha_state.state == STATE_ON
    assert ha_state.attributes["friendly_name"] == entity_name


async def test_hmip_reset_energy_counter_services(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory
) -> None:
    """Test reset_energy_counter service."""
    entity_id = "switch.pc"
    entity_name = "Pc"
    device_model = "HMIP-PSM"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=[entity_name]
    )

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )
    assert ha_state

    await hass.services.async_call(
        "homematicip_cloud",
        "reset_energy_counter",
        {"entity_id": "switch.pc"},
        blocking=True,
    )
    assert hmip_device.mock_calls[-1][0] == "reset_energy_counter_async"
    assert len(hmip_device._connection.mock_calls) == 1

    await hass.services.async_call(
        "homematicip_cloud", "reset_energy_counter", {"entity_id": "all"}, blocking=True
    )
    assert hmip_device.mock_calls[-1][0] == "reset_energy_counter_async"
    assert len(hmip_device._connection.mock_calls) == 2


async def test_hmip_multi_area_device(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    default_mock_hap_factory: HomeFactory,
) -> None:
    """Test multi area device. Check if devices are created and referenced."""
    entity_id = "binary_sensor.wired_eingangsmodul_32_fach_channel5"
    entity_name = "Wired Eingangsmodul – 32-fach Channel5"
    device_model = "HmIPW-DRI32"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=["Wired Eingangsmodul – 32-fach"]
    )

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )
    assert ha_state

    # get the entity
    entity = entity_registry.async_get(ha_state.entity_id)
    assert entity

    # get the device
    device = device_registry.async_get(entity.device_id)
    assert device.name == "Wired Eingangsmodul – 32-fach"

    # get the hap
    hap_device = device_registry.async_get(device.via_device_id)
    assert hap_device.name == "Home"
