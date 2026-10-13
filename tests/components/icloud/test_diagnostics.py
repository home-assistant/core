"""Tests for the iCloud diagnostics platform."""

from collections.abc import Awaitable, Callable

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.diagnostics import REDACTED
from homeassistant.components.icloud.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import DEVICE, LOCATION

from tests.common import MockConfigEntry
from tests.components.diagnostics import (
    get_diagnostics_for_config_entry,
    get_diagnostics_for_device,
)
from tests.typing import ClientSessionGenerator, MagicMock


async def test_config_entry_diagnostics(
    hass: HomeAssistant,
    icloud_service: MagicMock,
    devices_config_entry: MockConfigEntry,
    setup_entry: Callable[[Platform], Awaitable[None]],
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    icloud_service.devices.add({**DEVICE, "location": LOCATION})

    await setup_entry(Platform.SENSOR)

    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, devices_config_entry)
        == snapshot
    )


async def test_device_diagnostics(
    hass: HomeAssistant,
    icloud_service: MagicMock,
    devices_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    setup_entry: Callable[[Platform], Awaitable[None]],
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test device diagnostics."""
    icloud_service.devices.add({**DEVICE, "location": LOCATION})

    await setup_entry(Platform.SENSOR)

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, DEVICE["id"]), devices_config_entry.entry_id
    )
    assert device is not None

    assert (
        await get_diagnostics_for_device(
            hass, hass_client, devices_config_entry, device
        )
        == snapshot
    )


async def test_diagnostics_redacts_sensitive_data(
    hass: HomeAssistant,
    icloud_service: MagicMock,
    devices_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    setup_entry: Callable[[Platform], Awaitable[None]],
    hass_client: ClientSessionGenerator,
) -> None:
    """Diagnostics redact credentials, identity and location data."""
    icloud_service.devices.add(
        {
            **DEVICE,
            "name": "iPhone de John",
            "prsId": "johntravolta",
            "location": LOCATION,
            "lostDevice": {"text": "Call me", "ownerNbr": "+15551234567"},
        }
    )

    await setup_entry(Platform.SENSOR)

    entry_diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, devices_config_entry
    )

    assert entry_diagnostics["entry"]["data"]["username"] == REDACTED
    assert entry_diagnostics["entry"]["data"]["password"] == REDACTED
    assert entry_diagnostics["account"]["username"] == REDACTED
    assert entry_diagnostics["account"]["owner_fullname"] == REDACTED
    assert entry_diagnostics["account"]["family_members"] == REDACTED

    device_diagnostics = entry_diagnostics["devices"][0]
    assert device_diagnostics["id"] == REDACTED
    assert device_diagnostics["name"] == REDACTED
    assert device_diagnostics["prsId"] == REDACTED
    assert device_diagnostics["location"]["latitude"] == REDACTED
    assert device_diagnostics["location"]["longitude"] == REDACTED
    assert device_diagnostics["lostDevice"]["ownerNbr"] == REDACTED
    assert device_diagnostics["lostDevice"]["text"] == REDACTED

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, DEVICE["id"]), devices_config_entry.entry_id
    )
    assert device is not None

    device_only_diagnostics = await get_diagnostics_for_device(
        hass, hass_client, devices_config_entry, device
    )
    assert device_only_diagnostics["name"] == REDACTED
    assert device_only_diagnostics["location"]["latitude"] == REDACTED
