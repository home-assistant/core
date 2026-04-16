"""Init tests for stips_iru1."""

from unittest.mock import patch

import pytest

from homeassistant.components.stips_iru1 import (
    DOMAIN,
    StipsIru1RuntimeData,
    _register_catalog_devices,
    async_setup_entry,
    async_unload_entry,
)
from homeassistant.components.stips_iru1.const import PLATFORMS
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry


async def test_async_setup_entry_forwards_only_climate(
    hass: HomeAssistant,
) -> None:
    """Test integration forwards only the climate platform for initial core PR scope."""
    entry: MockConfigEntry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "devices": [
                {
                    "uniqueName": "stips-iru1-98eea1",
                    "name": "IR maze",
                    "remotes": [],
                }
            ]
        },
    )
    entry.add_to_hass(hass)

    with patch.object(
        hass.config_entries,
        "async_forward_entry_setups",
        return_value=True,
    ) as mock_forward:
        assert await hass.config_entries.async_setup(entry.entry_id)

    mock_forward.assert_called_once_with(entry, PLATFORMS)
    assert PLATFORMS == [Platform.CLIMATE]
    assert isinstance(entry.runtime_data, StipsIru1RuntimeData)
    assert entry.runtime_data.devices == entry.data["devices"]


async def test_async_setup_entry_raises_for_invalid_devices_data(
    hass: HomeAssistant,
) -> None:
    """Test setup raises a config entry error when devices data is invalid."""
    entry: MockConfigEntry = MockConfigEntry(
        domain=DOMAIN, data={"devices": {"invalid": "shape"}}
    )

    with (
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            return_value=True,
        ) as mock_forward,
        pytest.raises(ConfigEntryError),
    ):
        await async_setup_entry(hass, entry)

    mock_forward.assert_not_called()


def test_register_catalog_devices_creates_device_entries(hass: HomeAssistant) -> None:
    """Test catalog devices are registered with metadata."""
    entry: MockConfigEntry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "devices": [
                {
                    "uniqueName": "stips-iru1-98eea1",
                    "name": "Living Room IR",
                    "buildVersion": "1.2.3",
                    "areaName": "Living Room",
                },
                {
                    "name": "Missing unique name",
                },
            ]
        },
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.stips_iru1.normalize_device_mac",
        return_value="AA:BB:CC:DD:EE:FF",
    ):
        _register_catalog_devices(hass, entry)

    registry = dr.async_get(hass)
    device = registry.async_get_device(identifiers={(DOMAIN, "stips-iru1-98eea1")})

    assert device is not None
    assert device.name == "Living Room IR"
    assert device.sw_version == "1.2.3"
    assert device.suggested_area == "Living Room"
    assert (dr.CONNECTION_NETWORK_MAC, "aa:bb:cc:dd:ee:ff") in device.connections


async def test_async_unload_entry_unloads_platforms(hass: HomeAssistant) -> None:
    """Test unload delegates to platform unloading."""
    entry: MockConfigEntry = MockConfigEntry(domain=DOMAIN, data={"devices": []})

    with patch.object(
        hass.config_entries,
        "async_unload_platforms",
        return_value=True,
    ) as mock_unload:
        assert await async_unload_entry(hass, entry) is True

    mock_unload.assert_called_once_with(entry, PLATFORMS)
