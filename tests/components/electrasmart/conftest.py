"""Common fixtures for the Electra Smart tests."""

from unittest.mock import AsyncMock, Mock, patch

from electrasmart.device import OperationMode
from electrasmart.device.const import Feature
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.electrasmart.const import (
    CONF_IMEI,
    CONF_PHONE_NUMBER,
    DOMAIN,
)
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant


@pytest.fixture(name="mock_device")
def mock_device_fixture() -> Mock:
    """Return a mocked Electra AC device."""
    device = Mock(
        mac="a8032ab12345",
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
    device.name = "Living Room"
    return device


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
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_api: Mock
) -> None:
    """Set up the integration with a single mocked AC."""
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.electrasmart.ElectraAPI", return_value=mock_api
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
