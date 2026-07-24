"""Test select for ToGrill integration."""

from unittest.mock import Mock

import pytest
from syrupy.assertion import SnapshotAssertion
from togrill_bluetooth.packets import (
    GrillType,
    PacketA0Notify,
    PacketA8Notify,
    PacketA303Write,
    Taste,
)

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import TOGRILL_SERVICE_INFO, setup_entry

from tests.common import MockConfigEntry, snapshot_platform
from tests.components.bluetooth import inject_bluetooth_service_info


@pytest.mark.parametrize(
    "packets",
    [
        pytest.param([], id="no_data"),
        pytest.param(
            [
                PacketA0Notify(
                    battery=45,
                    version_major=1,
                    version_minor=5,
                    function_type=1,
                    probe_count=2,
                    ambient=False,
                    alarm_interval=5,
                    alarm_sound=True,
                ),
                PacketA8Notify(
                    probe=1,
                    alarm_type=0,
                    grill_type=1,
                ),
                PacketA8Notify(
                    probe=2,
                    alarm_type=0,
                    taste=1,
                ),
                PacketA8Notify(probe=2, alarm_type=None),
            ],
            id="probes_with_different_data",
        ),
        pytest.param(
            [
                PacketA8Notify(
                    probe=1,
                    alarm_type=0,
                    grill_type=99,
                ),
                PacketA8Notify(
                    probe=2,
                    alarm_type=0,
                    taste=99,
                ),
            ],
            id="probes_with_unknown_data",
        ),
    ],
)
async def test_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_entry: MockConfigEntry,
    mock_client: Mock,
    packets,
) -> None:
    """Test the setup."""

    inject_bluetooth_service_info(hass, TOGRILL_SERVICE_INFO)

    await setup_entry(hass, mock_entry, [Platform.SELECT])

    for packet in packets:
        mock_client.mocked_notify(packet)

    await snapshot_platform(hass, entity_registry, snapshot, mock_entry.entry_id)


@pytest.mark.parametrize(
    ("packets", "entity_id", "value", "write_packet"),
    [
        pytest.param(
            [
                PacketA8Notify(
                    probe=1,
                    alarm_type=PacketA8Notify.AlarmType.TEMPERATURE_TARGET,
                    temperature_1=50.0,
                ),
            ],
            "select.probe_1_grill_type",
            "veal",
            PacketA303Write(probe=1, grill_type=GrillType.VEAL, taste=None),
            id="grill_type",
        ),
        pytest.param(
            [
                PacketA8Notify(
                    probe=1,
                    alarm_type=PacketA8Notify.AlarmType.TEMPERATURE_TARGET,
                    grill_type=GrillType.BEEF,
                ),
            ],
            "select.probe_1_taste",
            "medium",
            PacketA303Write(probe=1, grill_type=GrillType.BEEF, taste=Taste.MEDIUM),
            id="taste",
        ),
        pytest.param(
            [
                PacketA8Notify(
                    probe=1,
                    alarm_type=PacketA8Notify.AlarmType.TEMPERATURE_TARGET,
                    grill_type=GrillType.BEEF,
                    taste=Taste.MEDIUM,
                ),
            ],
            "select.probe_1_taste",
            "none",
            PacketA303Write(probe=1, grill_type=GrillType.BEEF, taste=None),
            id="taste_none",
        ),
    ],
)
async def test_set_option(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    mock_client: Mock,
    packets,
    entity_id,
    value,
    write_packet,
) -> None:
    """Test the selection of option."""

    inject_bluetooth_service_info(hass, TOGRILL_SERVICE_INFO)

    await setup_entry(hass, mock_entry, [Platform.SELECT])

    for packet in packets:
        mock_client.mocked_notify(packet)

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        service_data={
            ATTR_OPTION: value,
        },
        target={
            ATTR_ENTITY_ID: entity_id,
        },
        blocking=True,
    )

    mock_client.write.assert_any_call(write_packet)
