"""Test for the SmartThings sensors platform."""

from unittest.mock import AsyncMock

from pysmartthings import Attribute, Capability
from pysmartthings.models import HealthStatus
import pytest
from syrupy import SnapshotAssertion

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
    setup_integration,
    snapshot_smartthings_entities,
    trigger_health_update,
    trigger_update,
)

from tests.common import MockConfigEntry


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

    assert hass.states.get("sensor.ac_office_granit_temperature").state == "25"

    await trigger_update(
        hass,
        devices,
        "96a5ef74-5832-a84b-f1f7-ca799957065d",
        Capability.TEMPERATURE_MEASUREMENT,
        Attribute.TEMPERATURE,
        20,
    )

    assert hass.states.get("sensor.ac_office_granit_temperature").state == "20"


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
    """Test we create an issue when an automation or script is using a deprecated entity."""
    issue_id = f"deprecated_{issue_string}_{entity_id}"

    entity_entry = entity_registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        unique_id,
        suggested_object_id=suggested_object_id,
        original_name=suggested_object_id,
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

    assert len(issue_registry.issues) == 1
    issue = issue_registry.async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.translation_key == f"deprecated_{issue_string}_scripts"
    assert issue.translation_placeholders == {
        "entity_id": entity_id,
        "entity_name": suggested_object_id,
        "items": "- [test](/config/automation/edit/test)\n- [test](/config/script/edit/test)",
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
    assert len(issue_registry.issues) == 0


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
    """Test we create an issue when an automation or script is using a deprecated entity."""
    issue_id = f"deprecated_{issue_string}_{entity_id}"

    entity_entry = entity_registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        unique_id,
        suggested_object_id=suggested_object_id,
        original_name=suggested_object_id,
    )

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(entity_id).state == expected_state

    assert len(issue_registry.issues) == 1
    issue = issue_registry.async_get_issue(DOMAIN, issue_id)
    assert issue is not None
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
    assert len(issue_registry.issues) == 0


@pytest.mark.parametrize("device_fixture", ["da_ac_rac_000001"])
async def test_availability(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test availability."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.ac_office_granit_temperature").state == "25"

    await trigger_health_update(
        hass, devices, "96a5ef74-5832-a84b-f1f7-ca799957065d", HealthStatus.OFFLINE
    )

    assert (
        hass.states.get("sensor.ac_office_granit_temperature").state
        == STATE_UNAVAILABLE
    )

    await trigger_health_update(
        hass, devices, "96a5ef74-5832-a84b-f1f7-ca799957065d", HealthStatus.ONLINE
    )

    assert hass.states.get("sensor.ac_office_granit_temperature").state == "25"


@pytest.mark.parametrize("device_fixture", ["da_ac_rac_000001"])
async def test_availability_at_start(
    hass: HomeAssistant,
    unavailable_device: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unavailable at boot."""
    await setup_integration(hass, mock_config_entry)
    assert (
        hass.states.get("sensor.ac_office_granit_temperature").state
        == STATE_UNAVAILABLE
    )
