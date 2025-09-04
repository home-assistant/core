"""Test numbers for ToGrill integration."""

from unittest.mock import Mock

from bleak.exc import BleakError
import pytest
from syrupy.assertion import SnapshotAssertion
from togrill_bluetooth.exceptions import BaseError
from togrill_bluetooth.packets import (
    PacketA0Notify,
    PacketA6Write,
    PacketA8Notify,
    PacketA300Write,
    PacketA301Write,
)

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
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
                    alarm_type=PacketA8Notify.AlarmType.TEMPERATURE_TARGET,
                    temperature_1=50.0,
                ),
                PacketA8Notify(probe=2, alarm_type=None),
            ],
            id="one_probe_with_target_alarm",
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
    """Test the numbers."""

    inject_bluetooth_service_info(hass, TOGRILL_SERVICE_INFO)

    await setup_entry(hass, mock_entry, [Platform.NUMBER])

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
            "number.probe_1_target_temperature",
            100.0,
            PacketA301Write(probe=1, target=100),
            id="probe",
        ),
        pytest.param(
            [
                PacketA8Notify(
                    probe=1,
                    alarm_type=PacketA8Notify.AlarmType.TEMPERATURE_TARGET,
                    temperature_1=50.0,
                ),
            ],
            "number.probe_1_target_temperature",
            0.0,
            PacketA301Write(probe=1, target=None),
            id="probe_clear",
        ),
        pytest.param(
            [
                PacketA8Notify(
                    probe=1,
                    alarm_type=PacketA8Notify.AlarmType.TEMPERATURE_RANGE,
                    temperature_1=50.0,
                    temperature_2=80.0,
                ),
            ],
            "number.probe_1_minimum_temperature",
            100.0,
            PacketA300Write(probe=1, minimum=100.0, maximum=80.0),
            id="minimum",
        ),
        pytest.param(
            [
                PacketA8Notify(
                    probe=1,
                    alarm_type=PacketA8Notify.AlarmType.TEMPERATURE_RANGE,
                    temperature_1=None,
                    temperature_2=80.0,
                ),
            ],
            "number.probe_1_minimum_temperature",
            0.0,
            PacketA300Write(probe=1, minimum=None, maximum=80.0),
            id="minimum_clear",
        ),
        pytest.param(
            [
                PacketA8Notify(
                    probe=1,
                    alarm_type=PacketA8Notify.AlarmType.TEMPERATURE_RANGE,
                    temperature_1=50.0,
                    temperature_2=80.0,
                ),
            ],
            "number.probe_1_maximum_temperature",
            100.0,
            PacketA300Write(probe=1, minimum=50.0, maximum=100.0),
            id="maximum",
        ),
        pytest.param(
            [
                PacketA8Notify(
                    probe=1,
                    alarm_type=PacketA8Notify.AlarmType.TEMPERATURE_RANGE,
                    temperature_1=50.0,
                    temperature_2=None,
                ),
            ],
            "number.probe_1_maximum_temperature",
            0.0,
            PacketA300Write(probe=1, minimum=50.0, maximum=None),
            id="maximum_clear",
        ),
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
                )
            ],
            "number.pro_05_alarm_interval",
            15,
            PacketA6Write(temperature_unit=None, alarm_interval=15),
            id="alarm_interval",
        ),
    ],
)
async def test_set_number(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    mock_client: Mock,
    packets,
    entity_id,
    value,
    write_packet,
) -> None:
    """Test the number set."""

    inject_bluetooth_service_info(hass, TOGRILL_SERVICE_INFO)

    await setup_entry(hass, mock_entry, [Platform.NUMBER])

    for packet in packets:
        mock_client.mocked_notify(packet)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        service_data={
            ATTR_VALUE: value,
        },
        target={
            ATTR_ENTITY_ID: entity_id,
        },
        blocking=True,
    )

    mock_client.write.assert_any_call(write_packet)


@pytest.mark.parametrize(
    ("error", "message"),
    [
        pytest.param(
            BleakError("Some error"),
            "Communication failed with the device",
            id="bleak",
        ),
        pytest.param(
            BaseError("Some error"),
            "Data was rejected by device",
            id="base",
        ),
    ],
)
async def test_set_number_write_error(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    mock_client: Mock,
    error,
    message,
) -> None:
    """Test the number set."""

    inject_bluetooth_service_info(hass, TOGRILL_SERVICE_INFO)

    await setup_entry(hass, mock_entry, [Platform.NUMBER])

    mock_client.mocked_notify(
        PacketA8Notify(
            probe=1,
            alarm_type=PacketA8Notify.AlarmType.TEMPERATURE_TARGET,
            temperature_1=50.0,
        ),
    )
    mock_client.write.side_effect = error

    with pytest.raises(HomeAssistantError, match=message):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            service_data={
                ATTR_VALUE: 100,
            },
            target={
                ATTR_ENTITY_ID: "number.probe_1_target_temperature",
            },
            blocking=True,
        )


async def test_set_number_disconnected(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    mock_client: Mock,
) -> None:
    """Test the number set."""

    inject_bluetooth_service_info(hass, TOGRILL_SERVICE_INFO)

    await setup_entry(hass, mock_entry, [Platform.NUMBER])

    mock_client.mocked_notify(
        PacketA8Notify(
            probe=1,
            alarm_type=PacketA8Notify.AlarmType.TEMPERATURE_TARGET,
            temperature_1=50.0,
        ),
    )
    mock_client.is_connected = False

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            service_data={
                ATTR_VALUE: 100,
            },
            target={
                ATTR_ENTITY_ID: "number.probe_1_target_temperature",
            },
            blocking=True,
        )
