"""Tests for Overkiz integration init."""
from homeassistant.components.overkiz.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from .test_config_flow import TEST_EMAIL, TEST_GATEWAY_ID, TEST_HUB, TEST_PASSWORD

from tests.common import MockConfigEntry, mock_registry

ENTITY_SENSOR_DISCRETE_RSSI_LEVEL = "sensor.zipscreen_woonkamer_discrete_rssi_level"
ENTITY_ALARM_CONTROL_PANEL = "alarm_control_panel.alarm"
ENTITY_SWITCH_GARAGE = "switch.garage"
ENTITY_SENSOR_TARGET_CLOSURE_STATE = "sensor.zipscreen_woonkamer_target_closure_state"
ENTITY_SENSOR_TARGET_CLOSURE_STATE_2 = (
    "sensor.zipscreen_woonkamer_target_closure_state_2"
)


async def test_unique_id_migration(hass: HomeAssistant) -> None:
    """Test migration of sensor unique IDs."""

    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_GATEWAY_ID,
        data={"username": TEST_EMAIL, "password": TEST_PASSWORD, "hub": TEST_HUB},
    )

    mock_entry.add_to_hass(hass)

    mock_registry(
        hass,
        {
            ENTITY_SENSOR_DISCRETE_RSSI_LEVEL: er.RegistryEntry(
                entity_id=ENTITY_SENSOR_DISCRETE_RSSI_LEVEL,
                unique_id="io://1234-5678-1234/3541212-OverkizState.CORE_DISCRETE_RSSI_LEVEL",
                platform=DOMAIN,
                config_entry_id=mock_entry.entry_id,
            ),
            ENTITY_ALARM_CONTROL_PANEL: er.RegistryEntry(
                entity_id=ENTITY_ALARM_CONTROL_PANEL,
                unique_id="internal://1234-5678-1234/alarm/0-UIWidget.TSKALARM_CONTROLLER",
                platform=DOMAIN,
                config_entry_id=mock_entry.entry_id,
            ),
            ENTITY_SWITCH_GARAGE: er.RegistryEntry(
                entity_id=ENTITY_SWITCH_GARAGE,
                unique_id="io://1234-5678-1234/0-UIClass.ON_OFF",
                platform=DOMAIN,
                config_entry_id=mock_entry.entry_id,
            ),
            ENTITY_SENSOR_TARGET_CLOSURE_STATE: er.RegistryEntry(
                entity_id=ENTITY_SENSOR_TARGET_CLOSURE_STATE,
                unique_id="io://xxxx-xxxx-xxxx/3541212-OverkizState.CORE_TARGET_CLOSURE",
                platform=DOMAIN,
                config_entry_id=mock_entry.entry_id,
            ),
            ENTITY_SENSOR_TARGET_CLOSURE_STATE_2: er.RegistryEntry(
                entity_id=ENTITY_SENSOR_TARGET_CLOSURE_STATE_2,
                unique_id="io://xxxx-xxxx-xxxx/3541212-core:TargetClosureState",
                platform=DOMAIN,
                config_entry_id=mock_entry.entry_id,
            ),
        },
    )
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    ent_reg = er.async_get(hass)

    # Test entity migrations
    # OverkizState enum
    sensor_discrete_rssi_level = ent_reg.async_get(ENTITY_SENSOR_DISCRETE_RSSI_LEVEL)
    assert (
        sensor_discrete_rssi_level.unique_id
        == "io://1234-5678-1234/3541212-core:DiscreteRSSILevelState"
    )

    # UIWidget enum
    alarm_control_panel = ent_reg.async_get(ENTITY_ALARM_CONTROL_PANEL)
    assert (
        alarm_control_panel.unique_id
        == "internal://1234-5678-1234/alarm/0-TSKAlarmController"
    )

    # UIClass enum
    switch_garage = ent_reg.async_get(ENTITY_SWITCH_GARAGE)
    assert switch_garage.unique_id == "io://1234-5678-1234/0-OnOff"

    # Test if duplicate entities will be removed
    duplicate_sensor_target_closure_state = ent_reg.async_get(
        ENTITY_SENSOR_TARGET_CLOSURE_STATE
    )
    assert duplicate_sensor_target_closure_state is None
