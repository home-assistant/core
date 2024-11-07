"""Common fixtures for the Airtouch 5 tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from airtouch5py.data_packet_factory import DataPacketFactory
from airtouch5py.packets.ac_ability import AcAbility
from airtouch5py.packets.ac_status import AcFanSpeed, AcMode, AcPowerState, AcStatus
from airtouch5py.packets.zone_name import ZoneName
from airtouch5py.packets.zone_status import (
    ControlMethod,
    ZonePowerState,
    ZoneStatusZone,
)
import pytest

from homeassistant.components.airtouch5.const import DOMAIN
from homeassistant.const import CONF_HOST

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.airtouch5.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock the config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="1.1.1.1",
        data={
            CONF_HOST: "1.1.1.1",
        },
    )


@pytest.fixture
def mock_airtouch5_client() -> Generator[AsyncMock]:
    """Mock an Airtouch5 client."""

    with (
        patch(
            "homeassistant.components.airtouch5.Airtouch5SimpleClient",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.airtouch5.config_flow.Airtouch5SimpleClient",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value

        # Default values for the tests using this mock :
        client.data_packet_factory = DataPacketFactory()
        client.ac = [
            AcAbility(
                ac_number=1,
                ac_name="AC 1",
                start_zone_number=1,
                zone_count=2,
                supports_mode_cool=True,
                supports_mode_fan=True,
                supports_mode_dry=True,
                supports_mode_heat=True,
                supports_mode_auto=True,
                supports_fan_speed_intelligent_auto=True,
                supports_fan_speed_turbo=True,
                supports_fan_speed_powerful=True,
                supports_fan_speed_high=True,
                supports_fan_speed_medium=True,
                supports_fan_speed_low=True,
                supports_fan_speed_quiet=True,
                supports_fan_speed_auto=True,
                min_cool_set_point=15,
                max_cool_set_point=25,
                min_heat_set_point=20,
                max_heat_set_point=30,
            )
        ]
        client.latest_ac_status = {
            1: AcStatus(
                ac_power_state=AcPowerState.ON,
                ac_number=1,
                ac_mode=AcMode.AUTO,
                ac_fan_speed=AcFanSpeed.AUTO,
                ac_setpoint=24,
                turbo_active=False,
                bypass_active=False,
                spill_active=False,
                timer_set=False,
                temperature=24,
                error_code=0,
            )
        }

        client.zones = [ZoneName(1, "Zone 1"), ZoneName(2, "Zone 2")]
        client.latest_zone_status = {
            1: ZoneStatusZone(
                zone_power_state=ZonePowerState.ON,
                zone_number=1,
                control_method=ControlMethod.PERCENTAGE_CONTROL,
                open_percentage=0.9,
                set_point=24,
                has_sensor=False,
                temperature=24,
                spill_active=False,
                is_low_battery=False,
            ),
            2: ZoneStatusZone(
                zone_power_state=ZonePowerState.ON,
                zone_number=1,
                control_method=ControlMethod.TEMPERATURE_CONTROL,
                open_percentage=1,
                set_point=24,
                has_sensor=True,
                temperature=24,
                spill_active=False,
                is_low_battery=False,
            ),
        }

        client.connection_state_callbacks = []
        client.zone_status_callbacks = []
        client.ac_status_callbacks = []

        yield client
