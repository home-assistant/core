"""Configuration for Ring tests."""

from collections.abc import Generator
from itertools import chain
from unittest.mock import AsyncMock, Mock, create_autospec, patch

import pytest
import ring_doorbell

from homeassistant.components.ring import DOMAIN
from homeassistant.components.ring.const import CONF_CONFIG_ENTRY_MINOR_VERSION
from homeassistant.const import CONF_DEVICE_ID, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .device_mocks import get_devices_data, get_mock_devices

from tests.common import MockConfigEntry
from tests.components.light.conftest import mock_light_profiles  # noqa: F401

MOCK_HARDWARE_ID = "foo-bar"


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.ring.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_ring_init_auth_class():
    """Mock ring_doorbell.Auth in init and return the mock class."""
    with patch("homeassistant.components.ring.Auth", autospec=True) as mock_ring_auth:
        mock_ring_auth.return_value.async_fetch_token.return_value = {
            "access_token": "mock-token"
        }
        yield mock_ring_auth


@pytest.fixture
def mock_ring_auth():
    """Mock ring_doorbell.Auth."""
    with patch(
        "homeassistant.components.ring.config_flow.Auth", autospec=True
    ) as mock_ring_auth:
        mock_ring_auth.return_value.async_fetch_token.return_value = {
            "access_token": "mock-token"
        }
        yield mock_ring_auth.return_value


@pytest.fixture
def mock_ring_devices():
    """Mock Ring devices."""

    devices = get_mock_devices()
    device_list = list(chain.from_iterable(devices.values()))

    def filter_devices(device_api_ai: int, device_family: set | None = None):
        return next(
            iter(
                [
                    device
                    for device in device_list
                    if device.id == device_api_ai
                    and (not device_family or device.family in device_family)
                ]
            )
        )

    class FakeRingDevices:
        """Class fakes the RingDevices class."""

        all_devices = device_list
        video_devices = (
            devices["stickup_cams"]
            + devices["doorbots"]
            + devices["authorized_doorbots"]
        )
        stickup_cams = devices["stickup_cams"]
        other = devices["other"]
        chimes = devices["chimes"]

        def get_device(self, id):
            return filter_devices(id)

        def get_video_device(self, id):
            return filter_devices(
                id, {"stickup_cams", "doorbots", "authorized_doorbots"}
            )

        def get_stickup_cam(self, id):
            return filter_devices(id, {"stickup_cams"})

        def get_other(self, id):
            return filter_devices(id, {"other"})

    return FakeRingDevices()


@pytest.fixture
def mock_ring_client(mock_ring_auth, mock_ring_devices):
    """Mock ring client api."""
    mock_client = create_autospec(ring_doorbell.Ring)
    mock_client.return_value.devices_data = get_devices_data()
    mock_client.return_value.devices.return_value = mock_ring_devices
    mock_client.return_value.active_alerts.return_value = []

    with patch("homeassistant.components.ring.Ring", new=mock_client):
        yield mock_client.return_value


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock ConfigEntry."""
    return MockConfigEntry(
        title="Ring",
        domain=DOMAIN,
        data={
            CONF_DEVICE_ID: MOCK_HARDWARE_ID,
            CONF_USERNAME: "foo@bar.com",
            "token": {"access_token": "mock-token"},
        },
        unique_id="foo@bar.com",
        version=1,
        minor_version=CONF_CONFIG_ENTRY_MINOR_VERSION,
    )


@pytest.fixture
async def mock_added_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ring_auth: Mock,
    mock_ring_client: Mock,
) -> MockConfigEntry:
    """Mock ConfigEntry that's been added to HA."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry


@pytest.fixture(autouse=True)
def mock_ring_event_listener_class():
    """Fixture to mock the ring event listener."""

    with patch(
        "homeassistant.components.ring.coordinator.RingEventListener", autospec=True
    ) as mock_ring_listener:
        mock_ring_listener.return_value.started = True
        yield mock_ring_listener
