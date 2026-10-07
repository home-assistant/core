from homeassistant.components.hunterdouglas_powerview.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry


async def test_remove_hub_device_is_blocked(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test that removing the root Hub device itself is strictly blocked."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="powerview_hub_123",
        data={"host": "192.168.1.50"},
    )
    config_entry.add_to_hass(hass)

    # Register the main hub device (via_device_id remains None)
    hub_device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "hub_serial_123")},
        name="PowerView Hub",
    )

    # Trigger Home Assistant's config entry device removal hook
    result = await hass.config_entries.async_remove_entry_device(
        config_entry, hub_device
    )

    # Assert that removal was blocked (returned False) and the device remains
    assert result is False
    assert device_registry.async_get(hub_device.id) is not None


async def test_remove_shade_device_is_allowed(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test that removing a shade device (child device) is permitted."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="powerview_hub_123",
        data={"host": "192.168.1.50"},
    )
    config_entry.add_to_hass(hass)

    # Register a parent hub device so we can link a shade to it
    hub_device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "hub_serial_123")},
        name="PowerView Hub",
    )

    # Register a shade device and explicitly assign it a via_device_id pointing to the hub
    shade_device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "shade_serial_999")},
        name="Living Room Shade",
        via_device_id=hub_device.id,
    )

    # Trigger Home Assistant's config entry device removal hook
    result = await hass.config_entries.async_remove_entry_device(
        config_entry, shade_device
    )

    # Assert that removal was successful (returned True) and it was dropped from the registry
    assert result is True
    assert device_registry.async_get(shade_device.id) is None
