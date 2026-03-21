"""Test Matter buttons."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, call

from chip.clusters import Objects as clusters
from chip.clusters.Types import NullValue
from matter_server.client.models.node import MatterNode
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .common import snapshot_matter_entities


@pytest.mark.usefixtures("matter_devices")
async def test_buttons(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test buttons."""
    snapshot_matter_entities(hass, entity_registry, snapshot, Platform.BUTTON)


@pytest.mark.parametrize("node_fixture", ["eve_energy_plug"])
async def test_identify_button(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test button entity is created for a Matter Identify Cluster."""
    state = hass.states.get("button.eve_energy_plug_identify")
    assert state
    assert state.attributes["friendly_name"] == "Eve Energy Plug Identify"
    # test press action
    await hass.services.async_call(
        "button",
        "press",
        {
            "entity_id": "button.eve_energy_plug_identify",
        },
        blocking=True,
    )
    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.Identify.Commands.Identify(identifyTime=15),
    )


@pytest.mark.parametrize("node_fixture", ["silabs_dishwasher"])
async def test_operational_state_buttons(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test if button entities are created for operational state commands."""
    assert hass.states.get("button.dishwasher_pause")
    assert hass.states.get("button.dishwasher_start")
    assert hass.states.get("button.dishwasher_stop")

    # resume may not be discovered as it's missing in the supported command list
    assert hass.states.get("button.dishwasher_resume") is None

    # test press action
    await hass.services.async_call(
        "button",
        "press",
        {
            "entity_id": "button.dishwasher_pause",
        },
        blocking=True,
    )
    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.OperationalState.Commands.Pause(),
    )


@pytest.mark.parametrize("node_fixture", ["heiman_smoke_detector"])
async def test_smoke_detector_self_test(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test button entity is created for a Matter SmokeCoAlarm Cluster."""
    state = hass.states.get("button.smoke_sensor_self_test")
    assert state
    assert state.attributes["friendly_name"] == "Smoke sensor Self-test"
    # test press action
    await hass.services.async_call(
        "button",
        "press",
        {
            "entity_id": "button.smoke_sensor_self_test",
        },
        blocking=True,
    )
    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.SmokeCoAlarm.Commands.SelfTestRequest(),
    )


@pytest.mark.freeze_time("2025-06-15T12:00:00+00:00")
@pytest.mark.parametrize("node_fixture", ["ikea_air_quality_monitor"])
async def test_time_sync_button(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test button entity is created for a Matter TimeSynchronization Cluster."""
    entity_id = "button.alpstuga_air_quality_monitor_sync_time"
    state = hass.states.get(entity_id)
    assert state
    assert state.attributes["friendly_name"] == "ALPSTUGA air quality monitor Sync time"
    # test press action
    await hass.services.async_call(
        "button",
        "press",
        {
            "entity_id": entity_id,
        },
        blocking=True,
    )
    assert matter_client.send_device_command.call_count == 3

    # Compute expected values based on HA's configured timezone
    chip_epoch = datetime(2000, 1, 1, tzinfo=UTC)
    frozen_now = datetime(2025, 6, 15, 12, 0, 0, tzinfo=UTC)
    delta = frozen_now - chip_epoch
    expected_utc_us = (
        (delta.days * 86400 * 1_000_000)
        + (delta.seconds * 1_000_000)
        + delta.microseconds
    )
    ha_tz = dt_util.get_default_time_zone()
    local_now = frozen_now.astimezone(ha_tz)
    utc_offset_delta = local_now.utcoffset()
    utc_offset = int(utc_offset_delta.total_seconds()) if utc_offset_delta else 0
    dst_offset_delta = local_now.dst()
    dst_offset = int(dst_offset_delta.total_seconds()) if dst_offset_delta else 0
    standard_offset = utc_offset - dst_offset

    # Verify SetTimeZone command
    assert matter_client.send_device_command.call_args_list[0] == call(
        node_id=matter_node.node_id,
        endpoint_id=0,
        command=clusters.TimeSynchronization.Commands.SetTimeZone(
            timeZone=[
                clusters.TimeSynchronization.Structs.TimeZoneStruct(
                    offset=standard_offset,
                    validAt=0,
                    name=str(ha_tz),
                )
            ]
        ),
    )
    # Verify SetDSTOffset command
    assert matter_client.send_device_command.call_args_list[1] == call(
        node_id=matter_node.node_id,
        endpoint_id=0,
        command=clusters.TimeSynchronization.Commands.SetDSTOffset(
            DSTOffset=[
                clusters.TimeSynchronization.Structs.DSTOffsetStruct(
                    offset=dst_offset,
                    validStarting=0,
                    validUntil=NullValue,
                )
            ]
        ),
    )
    # Verify SetUTCTime command
    assert matter_client.send_device_command.call_args_list[2] == call(
        node_id=matter_node.node_id,
        endpoint_id=0,
        command=clusters.TimeSynchronization.Commands.SetUTCTime(
            UTCTime=expected_utc_us,
            granularity=clusters.TimeSynchronization.Enums.GranularityEnum.kMicrosecondsGranularity,
        ),
    )
