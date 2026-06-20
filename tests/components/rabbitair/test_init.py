"""Test Rabbit Air integration setup."""

from collections.abc import Generator
from unittest.mock import MagicMock, Mock, patch

import pytest
from rabbitair import Mode, Model, Speed
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.rabbitair.const import DOMAIN
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST, CONF_MAC
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import format_mac

from tests.common import MockConfigEntry

TEST_HOST = "1.1.1.1"
TEST_TOKEN = "0123456789abcdef0123456789abcdef"
TEST_MAC = "01:23:45:67:89:AB"
TEST_FIRMWARE = "2.3.17"
TEST_HARDWARE = "1.0.0.4"
TEST_TITLE = "Rabbit Air"


@pytest.fixture(autouse=True)
def use_mocked_zeroconf(mock_async_zeroconf: MagicMock) -> None:
    """Mock zeroconf in all tests."""


def get_mock_state() -> Mock:
    """Return a mock device state instance."""
    mock_state = Mock()
    mock_state.model = Model.A3
    mock_state.main_firmware = TEST_HARDWARE
    mock_state.power = True
    mock_state.mode = Mode.Auto
    mock_state.speed = Speed.Low
    mock_state.wifi_firmware = TEST_FIRMWARE
    return mock_state


@pytest.fixture
def rabbitair_connect() -> Generator[None]:
    """Mock connection."""
    with patch("rabbitair.UdpClient.get_state", return_value=get_mock_state()):
        yield


@pytest.mark.usefixtures("rabbitair_connect")
async def test_device_registry(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the device registry entry, including the network MAC connection."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=TEST_TITLE,
        unique_id=format_mac(TEST_MAC),
        data={
            CONF_HOST: TEST_HOST,
            CONF_ACCESS_TOKEN: TEST_TOKEN,
            CONF_MAC: TEST_MAC,
        },
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    device_entry = device_registry.async_get_device(identifiers={(DOMAIN, TEST_MAC)})
    assert device_entry == snapshot
