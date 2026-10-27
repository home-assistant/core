"""Common fixtures for the Electra Smart tests."""

from unittest.mock import AsyncMock, Mock, patch

from electrasmart.device import OperationMode
from electrasmart.device.const import Feature
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.electrasmart.const import (
    CONF_IMEI,
    CONF_PHONE_NUMBER,
    DOMAIN,
)
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant


def _mock_device(mac: str, name: str) -> Mock:
    """Return a mocked Electra AC device."""
    device = Mock(
        mac=mac,
        model="Electra A/C",
        manufactor="Electra",
        features=[Feature.V_SWING, Feature.H_SWING],
        is_disconnected=Mock(return_value=False),
        is_on=Mock(return_value=False),
        is_horizontal_swing=Mock(return_value=False),
        is_vertical_swing=Mock(return_value=False),
        get_fan_speed=Mock(return_value=OperationMode.FAN_SPEED_AUTO),
        get_mode=Mock(return_value=OperationMode.MODE_COOL),
        get_sensor_temperature=Mock(return_value=24),
        get_temperature=Mock(return_value=22),
        get_shabat_mode=Mock(return_value=False),
        turn_on=Mock(return_value=True),
        turn_off=Mock(return_value=None),
        set_fan_speed=Mock(return_value=None),
        set_horizontal_swing=Mock(return_value=None),
        set_mode=Mock(return_value=None),
        set_shabat_mode=Mock(return_value=None),
        set_temperature=Mock(return_value=None),
        set_vertical_swing=Mock(return_value=None),
    )
    # `name` is a reserved Mock kwarg, so it must be set after construction.
    device.name = name
    return device


@pytest.fixture(name="mock_device")
def mock_device_fixture() -> Mock:
    """Return a mocked Electra AC device."""
    return _mock_device("a8032ab12345", "Living Room")


@pytest.fixture(name="second_device")
def second_device_fixture() -> Mock:
    """Return a second mocked AC on the same account."""
    return _mock_device("a8032ab67890", "Bedroom")


@pytest.fixture(name="mock_api")
def mock_api_fixture(mock_device: Mock) -> Mock:
    """Return a mocked Electra API holding a single AC."""
    return Mock(
        devices=[mock_device],
        fetch_devices=AsyncMock(),
        get_last_telemtry=AsyncMock(),
        set_state=AsyncMock(return_value={"status": 0, "data": {"res": 0}}),
    )


@pytest.fixture(name="config_entry")
def mock_config_entry() -> MockConfigEntry:
    """Return a config entry for an Electra account."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="0521234567",
        data={
            CONF_TOKEN: "token",
            CONF_IMEI: "2b950000024051000000000000000000",
            CONF_PHONE_NUMBER: "0521234567",
        },
    )


@pytest.fixture(name="setup_integration")
async def setup_integration(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_api: Mock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Set up the integration with a single mocked AC.

    Takes the freezer so that the integration is set up with a frozen clock:
    the coordinator schedules its polls against the event loop's clock, so a
    test that freezes only after setup would see a first poll immediately.
    """
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.electrasmart.ElectraAPI", return_value=mock_api
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
