"""Test HomematicIP Cloud valve entities."""

from unittest.mock import patch

from homematicip.base.enums import WaterSupplyState
from pytest_homeassistant.common import snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.valve import (
    DOMAIN as VALVE_DOMAIN,
    SERVICE_CLOSE_VALVE,
    SERVICE_OPEN_VALVE,
    ValveState,
)
from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .helper import HomeFactory, async_manipulate_test_data, get_and_check_entity_basics


async def test_watering_valve(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory
) -> None:
    """Test HomematicIP watering valve."""
    entity_id = "valve.bewaesserungsaktor_watering"
    entity_name = "Bewaesserungsaktor Watering"
    device_model = "ELV-SH-WSM"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=["Bewaesserungsaktor"]
    )

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )

    assert ha_state.state == ValveState.CLOSED

    await hass.services.async_call(
        VALVE_DOMAIN, SERVICE_OPEN_VALVE, {"entity_id": entity_id}, blocking=True
    )

    await async_manipulate_test_data(
        hass, hmip_device, "wateringActive", True, channel=1
    )
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == ValveState.OPEN


async def test_water_supply_valve(
    hass: HomeAssistant,
    default_mock_hap_factory: HomeFactory,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test HomematicIP water supply stop valve."""
    entity_id = "valve.wasserstopp"
    with patch(
        "homeassistant.components.homematicip_cloud.hap.PLATFORMS",
        [Platform.VALVE],
    ):
        mock_hap = await default_mock_hap_factory.async_get_mock_hap(
            test_devices=["Wasserstopp"], test_groups=[]
        )

    await snapshot_platform(
        hass, entity_registry, snapshot, mock_hap.config_entry.entry_id
    )

    hmip_device = mock_hap.hmip_device_by_entity_id[entity_id]
    channel = hmip_device.functionalChannels[1]

    await hass.services.async_call(
        VALVE_DOMAIN, SERVICE_CLOSE_VALVE, {"entity_id": entity_id}, blocking=True
    )
    assert channel.mock_calls[-1][0] == "set_water_supply_state_async"
    assert channel.mock_calls[-1][1] == (WaterSupplyState.NO_WATERFLOW,)
    await async_manipulate_test_data(
        hass, hmip_device, "waterSupplyState", WaterSupplyState.NO_WATERFLOW
    )
    assert hass.states.get(entity_id).state == ValveState.CLOSED

    await hass.services.async_call(
        VALVE_DOMAIN, SERVICE_OPEN_VALVE, {"entity_id": entity_id}, blocking=True
    )
    assert channel.mock_calls[-1][0] == "set_water_supply_state_async"
    assert channel.mock_calls[-1][1] == (WaterSupplyState.FULL_OPENED,)

    await async_manipulate_test_data(
        hass, hmip_device, "waterSupplyState", WaterSupplyState.REDUCED_WATERFLOW
    )
    assert hass.states.get(entity_id).state == ValveState.OPEN

    await async_manipulate_test_data(
        hass, hmip_device, "waterSupplyState", WaterSupplyState.UNKNOWN
    )
    assert hass.states.get(entity_id).state == STATE_UNKNOWN
