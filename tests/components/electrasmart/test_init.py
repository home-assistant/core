"""Tests for the Electra Smart integration setup."""

from unittest.mock import AsyncMock, Mock, patch

from electrasmart.device import OperationMode
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.electrasmart.const import (
    CONF_IMEI,
    CONF_PHONE_NUMBER,
    DOMAIN,
)
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry


@pytest.fixture(name="mock_device")
def mock_device_fixture() -> Mock:
    """Return a mocked Electra AC device."""
    device = Mock(
        mac="a8032ab12345",
        model="Electra A/C",
        manufactor="Electra",
        features=[],
        is_disconnected=Mock(return_value=False),
        is_on=Mock(return_value=False),
        is_horizontal_swing=Mock(return_value=False),
        is_vertical_swing=Mock(return_value=False),
        get_fan_speed=Mock(return_value=OperationMode.FAN_SPEED_AUTO),
        get_mode=Mock(return_value=OperationMode.MODE_COOL),
        get_sensor_temperature=Mock(return_value=24),
        get_temperature=Mock(return_value=22),
        get_shabat_mode=Mock(return_value=False),
    )
    # `name` is a reserved Mock kwarg, so it must be set after construction.
    device.name = "Living Room"
    return device


async def test_device_registry(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_device: Mock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the device registry entry, including the network MAC connection."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="0521234567",
        data={
            CONF_TOKEN: "token",
            CONF_IMEI: "2b950000024051000000000000000000",
            CONF_PHONE_NUMBER: "0521234567",
        },
    )
    entry.add_to_hass(hass)

    mock_api = Mock(devices=[mock_device], fetch_devices=AsyncMock())
    with patch(
        "homeassistant.components.electrasmart.ElectraAPI", return_value=mock_api
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, "a8032ab12345")}
    )
    assert device_entry == snapshot
