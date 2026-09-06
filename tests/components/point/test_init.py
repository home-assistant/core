"""Tests for the Point component."""

import time
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.application_credentials import (
    DOMAIN as APPLICATION_CREDENTIALS_DOMAIN,
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.point import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
)
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

HOME_ID = "home_1"
DEVICE_ID = "device_1"

DEVICE_RAW: dict[str, Any] = {
    "device_id": DEVICE_ID,
    "device_mac": "00:11:22:33:44:55",
    "description": "Kitchen",
    "hardware_version": "1",
    "firmware": {"installed": "2.0.0"},
    "home": HOME_ID,
    "last_heard_from_at": "2023-01-01T00:00:00+00:00",
    "active": True,
    "offline": False,
    "battery": {"percent": 100},
    "ongoing_events": [],
}

HOME_RAW: dict[str, Any] = {
    "home_id": HOME_ID,
    "name": "My Home",
    "devices": [DEVICE_ID],
    "alarm_status": "off",
}


class FakeDevice:
    """Minimal fake of pypoint.Device."""

    def __init__(self, raw: dict[str, Any]) -> None:
        """Initialize."""
        self._raw = raw

    @property
    def device_id(self) -> str:
        """Return the device id."""
        return self._raw["device_id"]

    @property
    def device(self) -> dict[str, Any]:
        """Return the raw representation."""
        return self._raw

    @property
    def name(self) -> str:
        """Return the device name."""
        return self._raw["description"]

    @property
    def last_update(self) -> str:
        """Return the last update timestamp."""
        return self._raw["last_heard_from_at"]

    @property
    def ongoing_events(self) -> list[str]:
        """Return ongoing events."""
        return self._raw["ongoing_events"]

    @property
    def webhook(self) -> str:
        """Return the webhook."""
        return "webhook"

    @property
    def device_status(self) -> dict[str, Any]:
        """Return the device status."""
        return {
            "active": self._raw["active"],
            "offline": self._raw["offline"],
            "last_update": self.last_update,
            "battery_level": self._raw["battery"]["percent"],
        }

    async def sensor(self, sensor_type: str) -> float:
        """Return a sensor value."""
        return 1.0


class FakePointSession:
    """Minimal fake of pypoint.PointSession."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize."""
        self._devices = {DEVICE_ID: DEVICE_RAW}
        self._homes = {HOME_ID: HOME_RAW}
        self.webhook = "webhook"

    async def update(self) -> bool:
        """Update the session."""
        return True

    @property
    def homes(self) -> dict[str, dict[str, Any]]:
        """Return known homes."""
        return self._homes

    @property
    def device_ids(self) -> Any:
        """Return known device ids."""
        return self._devices.keys()

    @property
    def devices(self) -> Any:
        """Return device representations."""
        return (FakeDevice(raw) for raw in self._devices.values())

    def device(self, device_id: str) -> FakeDevice:
        """Return a single device."""
        return FakeDevice(self._devices[device_id])


@pytest.fixture
async def setup_credentials(hass: HomeAssistant) -> None:
    """Fixture to set up application credentials."""
    assert await async_setup_component(hass, APPLICATION_CREDENTIALS_DOMAIN, {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential("1234", "5678"),
    )


async def test_oauth_implementation_not_available(
    hass: HomeAssistant,
) -> None:
    """Test that unavailable OAuth implementation raises ConfigEntryNotReady."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "refresh_token": "mock-refresh-token",
                "access_token": "mock-access-token",
                "type": "Bearer",
                "expires_in": 60,
            },
        },
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.point.async_get_config_entry_implementation",
        side_effect=ImplementationUnavailableError,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("setup_credentials")
async def test_device_via_device_link(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that a Point device is linked to its home via_device."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="abcd",
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "refresh_token": "mock-refresh-token",
                "access_token": "mock-access-token",
                "type": "Bearer",
                "expires_in": 60,
                "expires_at": time.time() + 3600,
            },
        },
    )
    config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.point.PointSession",
            FakePointSession,
        ),
        patch(
            "homeassistant.components.point.async_setup_webhook",
            new=AsyncMock(),
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    home_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, HOME_ID), config_entry.entry_id
    )
    assert home_device is not None

    point_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, DEVICE_ID), config_entry.entry_id
    )
    assert point_device is not None
    assert point_device.via_device_id == home_device.id
