"""Test Airthings devices, and ensure old devices are removed."""

from unittest.mock import patch

from airthings import AirthingsError

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import MockAirthings, setup_integration
from .const import TEST_DATA, THREE_DEVICES, TWO_DEVICES


async def test_setup_integration(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that the Airthings integration is set up correctly."""

    with patch(
        "homeassistant.components.airthings.Airthings",
        return_value=MockAirthings(TWO_DEVICES),
    ):
        entry = await setup_integration(hass)

    assert entry is not None
    assert entry.domain == "airthings"
    assert entry.data == TEST_DATA
    assert len(device_registry.devices) == len(TWO_DEVICES)


async def test_add_new_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that a new Airthings device is added correctly."""

    with patch(
        "homeassistant.components.airthings.Airthings",
        return_value=MockAirthings(TWO_DEVICES),
    ):
        entry = await setup_integration(hass)

    assert entry is not None
    assert entry.domain == "airthings"
    assert entry.data == TEST_DATA
    assert len(device_registry.devices) == len(TWO_DEVICES)

    # Add device
    with patch(
        "homeassistant.components.airthings.Airthings",
        return_value=MockAirthings(THREE_DEVICES),
    ):
        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()

    assert len(device_registry.devices) == len(THREE_DEVICES)


async def test_setup_integration_no_devices(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that the Airthings integration handles no devices correctly."""

    with patch(
        "homeassistant.components.airthings.Airthings",
        return_value=MockAirthings({}),
    ):
        entry = await setup_integration(hass)

    assert entry is not None
    assert entry.domain == "airthings"
    assert entry.data == TEST_DATA
    assert len(device_registry.devices) == 0


async def test_remove_old_devices(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that old devices are removed when new data is fetched."""

    with patch(
        "homeassistant.components.airthings.Airthings",
        return_value=MockAirthings(THREE_DEVICES),
    ):
        entry = await setup_integration(hass)

    assert entry is not None
    assert entry.domain == "airthings"
    assert entry.data == TEST_DATA
    assert len(device_registry.devices) == len(THREE_DEVICES)

    with patch(
        "homeassistant.components.airthings.Airthings",
        return_value=MockAirthings(TWO_DEVICES),
    ):
        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()

    assert len(device_registry.devices) == len(TWO_DEVICES)


async def test_failing_api_call(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that the integration handles API call failures gracefully."""

    with patch(
        "homeassistant.components.airthings.Airthings",
        return_value=MockAirthings(THREE_DEVICES),
    ):
        entry = await setup_integration(hass)

    assert len(device_registry.devices) == len(THREE_DEVICES)

    # Simulate an API failure
    with patch(
        "homeassistant.components.airthings.Airthings.update_devices",
        side_effect=AirthingsError("API call failed"),
    ):
        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()

    assert len(device_registry.devices) == len(THREE_DEVICES)
