"""Test for the SmartThings sensors platform."""

from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from pysmartthings import Attribute, Capability
from pysmartthings.models import HealthStatus
import pytest
from pytest_homeassistant.common import MockConfigEntry
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import automation, script
from homeassistant.components.automation import automations_with_entity
from homeassistant.components.script import scripts_with_entity
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.smartthings.const import DOMAIN, MAIN
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.setup import async_setup_component

from . import (
    set_attribute_value,
    setup_integration,
    snapshot_smartthings_entities,
    trigger_health_update,
    trigger_update,
)


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    await setup_integration(hass, mock_config_entry)

    snapshot_smartthings_entities(hass, entity_registry, snapshot, Platform.SENSOR)


@pytest.mark.parametrize("device_fixture", ["da_ac_rac_000001"])
async def test_state_update(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test state update."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.theater_ac_office_granit_temperature").state == "25"

    await trigger_update(
        hass,
        devices,
        "96a5ef74-5832-a84b-f1f7-ca799957065d",
        Capability.TEMPERATURE_MEASUREMENT,
        Attribute.TEMPERATURE,
        20,
    )

    assert hass.states.get("sensor.theater_ac_office_granit_temperature").state == "20"


@pytest.mark.parametrize("device_fixture", ["multipurpose_sensor"])
async def test_three_axis_none_value(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test three axis coordinate sensors handle a None value."""
    set_attribute_value(devices, Capability.THREE_AXIS, Attribute.THREE_AXIS, None)

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.theater_deck_door_x_coordinate").state == (
        STATE_UNKNOWN
    )
    assert hass.states.get("sensor.theater_deck_door_y_coordinate").state == (
        STATE_UNKNOWN
    )
    assert hass.states.get("sensor.theater_deck_door_z_coordinate").state == (
        STATE_UNKNOWN
    )


@pytest.mark.parametrize(
    (
        "device_fixture",
        "unique_id",
        "suggested_object_id",
        "issue_string",
        "entity_id",
        "expected_state",
        "version",
    ),
    [
        (
            "vd_stv_2017_k",
            f"4588d2d9-a8cf-40f4-9a0b-ed5dfbaccda1_{MAIN}_{Capability.MEDIA_PLAYBACK}_{Attribute.PLAYBACK_STATUS}_{Attribute.PLAYBACK_STATUS}",
            "tv_samsung_8_series_49_media_playback_status",
            "media_player",
            "sensor.tv_samsung_8_series_49_media_playback_status",
            STATE_UNKNOWN,
            "2025.10.0",
        ),
        (
            "vd_stv_2017_k",
            f"4588d2d9-a8cf-40f4-9a0b-ed5dfbaccda1_{MAIN}_{Capability.AUDIO_VOLUME}_{Attribute.VOLUME}_{Attribute.VOLUME}",
            "tv_samsung_8_series_49_volume",
            "media_player",
            "sensor.tv_samsung_8_series_49_volume",
            "13",
            "2025.10.0",
        ),
        (
            "vd_stv_2017_k",
            f"4588d2d9-a8cf-40f4-9a0b-ed5dfbaccda1_{MAIN}_{Capability.MEDIA_INPUT_SOURCE}_{Attribute.INPUT_SOURCE}_{Attribute.INPUT_SOURCE}",
            "tv_samsung_8_series_49_media_input_source",
            "media_player",
            "sensor.tv_samsung_8_series_49_media_input_source",
            "hdmi1",
            "2025.10.0",
        ),
        (
            "im_speaker_ai_0001",
            f"c9276e43-fe3c-88c3-1dcc-2eb79e292b8c_{MAIN}_{Capability.MEDIA_PLAYBACK_REPEAT}_{Attribute.PLAYBACK_REPEAT_MODE}_{Attribute.PLAYBACK_REPEAT_MODE}",
            "galaxy_home_mini_media_playback_repeat",
            "media_player",
            "sensor.galaxy_home_mini_media_playback_repeat",
            "off",
            "2025.10.0",
        ),
        (
            "im_speaker_ai_0001",
            f"c9276e43-fe3c-88c3-1dcc-2eb79e292b8c_{MAIN}_{Capability.MEDIA_PLAYBACK_SHUFFLE}_{Attribute.PLAYBACK_SHUFFLE}_{Attribute.PLAYBACK_SHUFFLE}",
            "galaxy_home_mini_media_playback_shuffle",
            "media_player",
            "sensor.galaxy_home_mini_media_playback_shuffle",
            "disabled",
            "2025.10.0",
        ),
        (
            "da_ac_ehs_01001",
            f"4165c51e-bf6b-c5b6-fd53-127d6248754b_{MAIN}_{Capability.TEMPERATURE_MEASUREMENT}_{Attribute.TEMPERATURE}_{Attribute.TEMPERATURE}",
            "temperature",
            "dhw",
            "sensor.temperature",
            "57",
            "2025.12.0",
        ),
        (
            "da_ac_ehs_01001",
            f"4165c51e-bf6b-c5b6-fd53-127d6248754b_{MAIN}_{Capability.THERMOSTAT_COOLING_SETPOINT}_{Attribute.COOLING_SETPOINT}_{Attribute.COOLING_SETPOINT}",
            "cooling_setpoint",
            "dhw",
            "sensor.cooling_setpoint",
            "56",
            "2025.12.0",
        ),
    ],
)
async def test_create_issue_with_items(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    unique_id: str,
    suggested_object_id: str,
    issue_string: str,
    entity_id: str,
    expected_state: str,
    version: str,
) -> None:
    """Test issue for automation/script using deprecated entity."""
    issue_id = f"deprecated_{issue_string}_{entity_id}"

    mock_config_entry.add_to_hass(hass)
    entity_entry = entity_registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        unique_id,
        suggested_object_id=suggested_object_id,
        original_name=suggested_object_id,
        config_entry=mock_config_entry,
    )

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "id": "test",
                "alias": "test",
                "trigger": {"platform": "state", "entity_id": entity_id},
                "action": {
                    "action": "automation.turn_on",
                    "target": {
                        "entity_id": "automation.test",
                    },
                },
            }
        },
    )
    assert await async_setup_component(
        hass,
        script.DOMAIN,
        {
            script.DOMAIN: {
                "test": {
                    "sequence": [
                        {
                            "condition": "state",
                            "entity_id": entity_id,
                            "state": "on",
                        },
                    ],
                }
            }
        },
    )

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(entity_id).state == expected_state

    assert automations_with_entity(hass, entity_id)[0] == "automation.test"
    assert scripts_with_entity(hass, entity_id)[0] == "script.test"

    issue = issue_registry.async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.config_entry_id == mock_config_entry.entry_id
    assert issue.translation_key == f"deprecated_{issue_string}_scripts"
    assert issue.translation_placeholders == {
        "entity_id": entity_id,
        "entity_name": suggested_object_id,
        "items": (
            "- [test](/config/automation/edit/test)\n- [test](/config/script/edit/test)"
        ),
    }
    assert issue.breaks_in_ha_version == version

    entity_registry.async_update_entity(
        entity_entry.entity_id,
        disabled_by=er.RegistryEntryDisabler.USER,
    )

    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Assert the issue is no longer present
    assert not issue_registry.async_get_issue(DOMAIN, issue_id)


@pytest.mark.parametrize(
    (
        "device_fixture",
        "unique_id",
        "suggested_object_id",
        "issue_string",
        "entity_id",
        "expected_state",
        "version",
    ),
    [
        (
            "vd_stv_2017_k",
            f"4588d2d9-a8cf-40f4-9a0b-ed5dfbaccda1_{MAIN}_{Capability.MEDIA_PLAYBACK}_{Attribute.PLAYBACK_STATUS}_{Attribute.PLAYBACK_STATUS}",
            "tv_samsung_8_series_49_media_playback_status",
            "media_player",
            "sensor.tv_samsung_8_series_49_media_playback_status",
            STATE_UNKNOWN,
            "2025.10.0",
        ),
        (
            "vd_stv_2017_k",
            f"4588d2d9-a8cf-40f4-9a0b-ed5dfbaccda1_{MAIN}_{Capability.AUDIO_VOLUME}_{Attribute.VOLUME}_{Attribute.VOLUME}",
            "tv_samsung_8_series_49_volume",
            "media_player",
            "sensor.tv_samsung_8_series_49_volume",
            "13",
            "2025.10.0",
        ),
        (
            "vd_stv_2017_k",
            f"4588d2d9-a8cf-40f4-9a0b-ed5dfbaccda1_{MAIN}_{Capability.MEDIA_INPUT_SOURCE}_{Attribute.INPUT_SOURCE}_{Attribute.INPUT_SOURCE}",
            "tv_samsung_8_series_49_media_input_source",
            "media_player",
            "sensor.tv_samsung_8_series_49_media_input_source",
            "hdmi1",
            "2025.10.0",
        ),
        (
            "im_speaker_ai_0001",
            f"c9276e43-fe3c-88c3-1dcc-2eb79e292b8c_{MAIN}_{Capability.MEDIA_PLAYBACK_REPEAT}_{Attribute.PLAYBACK_REPEAT_MODE}_{Attribute.PLAYBACK_REPEAT_MODE}",
            "galaxy_home_mini_media_playback_repeat",
            "media_player",
            "sensor.galaxy_home_mini_media_playback_repeat",
            "off",
            "2025.10.0",
        ),
        (
            "im_speaker_ai_0001",
            f"c9276e43-fe3c-88c3-1dcc-2eb79e292b8c_{MAIN}_{Capability.MEDIA_PLAYBACK_SHUFFLE}_{Attribute.PLAYBACK_SHUFFLE}_{Attribute.PLAYBACK_SHUFFLE}",
            "galaxy_home_mini_media_playback_shuffle",
            "media_player",
            "sensor.galaxy_home_mini_media_playback_shuffle",
            "disabled",
            "2025.10.0",
        ),
        (
            "da_ac_ehs_01001",
            f"4165c51e-bf6b-c5b6-fd53-127d6248754b_{MAIN}_{Capability.TEMPERATURE_MEASUREMENT}_{Attribute.TEMPERATURE}_{Attribute.TEMPERATURE}",
            "temperature",
            "dhw",
            "sensor.temperature",
            "57",
            "2025.12.0",
        ),
        (
            "da_ac_ehs_01001",
            f"4165c51e-bf6b-c5b6-fd53-127d6248754b_{MAIN}_{Capability.THERMOSTAT_COOLING_SETPOINT}_{Attribute.COOLING_SETPOINT}_{Attribute.COOLING_SETPOINT}",
            "cooling_setpoint",
            "dhw",
            "sensor.cooling_setpoint",
            "56",
            "2025.12.0",
        ),
    ],
)
async def test_create_issue(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    unique_id: str,
    suggested_object_id: str,
    issue_string: str,
    entity_id: str,
    expected_state: str,
    version: str,
) -> None:
    """Test issue for automation/script using deprecated entity."""
    issue_id = f"deprecated_{issue_string}_{entity_id}"

    mock_config_entry.add_to_hass(hass)
    entity_entry = entity_registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        unique_id,
        suggested_object_id=suggested_object_id,
        original_name=suggested_object_id,
        config_entry=mock_config_entry,
    )

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(entity_id).state == expected_state

    issue = issue_registry.async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.config_entry_id == mock_config_entry.entry_id
    assert issue.translation_key == f"deprecated_{issue_string}"
    assert issue.translation_placeholders == {
        "entity_id": entity_id,
        "entity_name": suggested_object_id,
    }
    assert issue.breaks_in_ha_version == version

    entity_registry.async_update_entity(
        entity_entry.entity_id,
        disabled_by=er.RegistryEntryDisabler.USER,
    )

    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Assert the issue is no longer present
    assert not issue_registry.async_get_issue(DOMAIN, issue_id)


@pytest.mark.parametrize("device_fixture", ["da_ac_rac_000001"])
async def test_availability(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test availability."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.theater_ac_office_granit_temperature").state == "25"

    await trigger_health_update(
        hass, devices, "96a5ef74-5832-a84b-f1f7-ca799957065d", HealthStatus.OFFLINE
    )

    assert (
        hass.states.get("sensor.theater_ac_office_granit_temperature").state
        == STATE_UNAVAILABLE
    )

    await trigger_health_update(
        hass, devices, "96a5ef74-5832-a84b-f1f7-ca799957065d", HealthStatus.ONLINE
    )

    assert hass.states.get("sensor.theater_ac_office_granit_temperature").state == "25"


@pytest.mark.parametrize("device_fixture", ["da_ac_rac_000001"])
async def test_availability_at_start(
    hass: HomeAssistant,
    unavailable_device: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unavailable at boot."""
    await setup_integration(hass, mock_config_entry)
    assert (
        hass.states.get("sensor.theater_ac_office_granit_temperature").state
        == STATE_UNAVAILABLE
    )


@pytest.mark.parametrize("device_fixture", ["da_vc_stick_01001"])
@pytest.mark.parametrize(
    ("reported_state", "expected_state"),
    [
        ("usingVacuum", "using_vacuum"),
        ("emptyingDustbin", "emptying_dustbin"),
        ("UVCleaning", "uv_cleaning"),
        ("UVPaused", "uv_paused"),
        ("ready", "ready"),
    ],
)
async def test_stick_cleaner_operating_state_is_mapped(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    reported_state: str,
    expected_state: str,
) -> None:
    """Test the stick cleaner states are mapped onto the entity options."""
    await setup_integration(hass, mock_config_entry)

    await trigger_update(
        hass,
        devices,
        "e1f93c0c-6fe0-c65a-a314-c8f7b163c86b",
        Capability.SAMSUNG_CE_STICK_CLEANER_STATUS,
        Attribute.OPERATING_STATE,
        reported_state,
    )

    assert (state := hass.states.get("sensor.stick_vacuum"))
    assert state.state == expected_state


@pytest.mark.parametrize("device_fixture", ["da_wm_wm_000001"])
async def test_partial_power_consumption_report(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a partial report with a negative energy value does not crash."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.theater_washer_energy").state == "352.8"
    assert hass.states.get("sensor.theater_washer_power").state == "0"

    await trigger_update(
        hass,
        devices,
        "f984b91d-f250-9d42-3436-33f09a422a47",
        Capability.POWER_CONSUMPTION_REPORT,
        Attribute.POWER_CONSUMPTION,
        {"energy": -1},
    )

    assert hass.states.get("sensor.theater_washer_energy").state == STATE_UNKNOWN
    assert hass.states.get("sensor.theater_washer_power").state == STATE_UNKNOWN
    assert hass.states.get("sensor.theater_washer_energy_saved").state == STATE_UNKNOWN


@pytest.mark.parametrize("device_fixture", ["da_wm_wm_000001"])
async def test_negative_power_consumption_values(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test negative values are unknown only for always increasing sensors."""
    await setup_integration(hass, mock_config_entry)

    await trigger_update(
        hass,
        devices,
        "f984b91d-f250-9d42-3436-33f09a422a47",
        Capability.POWER_CONSUMPTION_REPORT,
        Attribute.POWER_CONSUMPTION,
        {
            "energy": 352800,
            "power": 0,
            "energySaved": -5,
            "deltaEnergy": -200,
            "powerEnergy": -300,
        },
    )

    assert hass.states.get("sensor.theater_washer_energy_saved").state == STATE_UNKNOWN
    assert hass.states.get("sensor.theater_washer_energy_difference").state == "-0.2"
    assert hass.states.get("sensor.theater_washer_power_energy").state == "-0.3"


@pytest.mark.parametrize("device_fixture", ["da_wm_dw_000001"])
@pytest.mark.parametrize(
    ("reported_state", "expected_state"),
    [
        ("none", "none"),
        ("delayWashing", "delay_washing"),
        ("preWashing", "pre_washing"),
        ("washing", "washing"),
        ("dryingAutoReleaseDelay", "drying_auto_release_delay"),
        ("autoReleaseDrying", "auto_release_drying"),
        ("finished", "finished"),
    ],
)
async def test_dishwasher_detailed_job_state(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    reported_state: str,
    expected_state: str,
) -> None:
    """Test the Samsung dishwasher job states are mapped onto the entity options."""
    await setup_integration(hass, mock_config_entry)

    await trigger_update(
        hass,
        devices,
        "f36dc7ce-cac0-0667-dc14-a3704eb5e676",
        Capability.SAMSUNG_CE_DISHWASHER_JOB_STATE,
        Attribute.DISHWASHER_JOB_STATE,
        reported_state,
    )

    assert (state := hass.states.get("sensor.theater_dishwasher_detailed_job_state"))
    assert state.state == expected_state


@pytest.mark.parametrize("device_fixture", ["da_wm_dw_000001"])
async def test_dishwasher_delayed_start_time(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the delayed start time is derived from the minutes left to start."""
    freezer.move_to("2023-10-21T10:00:30+00:00")
    await setup_integration(hass, mock_config_entry)

    entity_id = "sensor.theater_dishwasher_delayed_start_time"
    assert hass.states.get(entity_id).state == STATE_UNKNOWN

    await trigger_update(
        hass,
        devices,
        "f36dc7ce-cac0-0667-dc14-a3704eb5e676",
        Capability.SAMSUNG_CE_DISHWASHER_OPERATION,
        Attribute.TIME_LEFT_TO_START,
        488.0,
    )

    assert hass.states.get(entity_id).state == "2023-10-21T18:08:00+00:00"

    # The device counts down every minute, the start time stays the same
    freezer.tick(timedelta(minutes=1))
    await trigger_update(
        hass,
        devices,
        "f36dc7ce-cac0-0667-dc14-a3704eb5e676",
        Capability.SAMSUNG_CE_DISHWASHER_OPERATION,
        Attribute.TIME_LEFT_TO_START,
        487.0,
    )

    assert hass.states.get(entity_id).state == "2023-10-21T18:08:00+00:00"

    await trigger_update(
        hass,
        devices,
        "f36dc7ce-cac0-0667-dc14-a3704eb5e676",
        Capability.SAMSUNG_CE_DISHWASHER_OPERATION,
        Attribute.TIME_LEFT_TO_START,
        0.0,
    )

    assert hass.states.get(entity_id).state == STATE_UNKNOWN
