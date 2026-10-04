"""Tests for the Dyson Infrared config entry setup/unload."""

from unittest.mock import patch

import pytest

from homeassistant.components.dyson_infrared.const import (
    CONF_DEVICE_TYPE,
    DysonDeviceType,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("device_type", "platform"),
    [
        (DysonDeviceType.FAN, Platform.FAN),
        (DysonDeviceType.HEATER_COOLER, Platform.CLIMATE),
    ],
)
async def test_async_setup_entry(
    hass: HomeAssistant, device_type: DysonDeviceType, platform: Platform
) -> None:
    """Test setting up the Dyson Infrared config entry forwards the right platform."""
    entry = MockConfigEntry(
        domain="dyson_infrared", data={CONF_DEVICE_TYPE: device_type}
    )
    entry.add_to_hass(hass)

    with patch.object(
        hass.config_entries, "async_forward_entry_setups"
    ) as mock_forward:
        result = await hass.config_entries.async_setup(entry.entry_id)

        assert result is True
        mock_forward.assert_called_once_with(entry, [platform])


@pytest.mark.parametrize(
    ("device_type", "platform"),
    [
        (DysonDeviceType.FAN, Platform.FAN),
        (DysonDeviceType.HEATER_COOLER, Platform.CLIMATE),
    ],
)
async def test_async_unload_entry(
    hass: HomeAssistant, device_type: DysonDeviceType, platform: Platform
) -> None:
    """Test unloading a config entry forwards unload to the right platform."""
    entry = MockConfigEntry(
        domain="dyson_infrared", data={CONF_DEVICE_TYPE: device_type}
    )
    entry.add_to_hass(hass)

    with patch.object(hass.config_entries, "async_forward_entry_setups"):
        await hass.config_entries.async_setup(entry.entry_id)

    with patch.object(
        hass.config_entries, "async_unload_platforms", return_value=True
    ) as mock_unload:
        result = await hass.config_entries.async_unload(entry.entry_id)

        assert result is True
        mock_unload.assert_called_once_with(entry, [platform])


@pytest.mark.parametrize(
    "data",
    [
        pytest.param({}, id="missing"),
        pytest.param({CONF_DEVICE_TYPE: "purifier"}, id="unrecognized"),
    ],
)
async def test_async_setup_entry_unknown_device_type(
    hass: HomeAssistant, data: dict[str, str]
) -> None:
    """Test an entry without a usable device type fails setup with a clear error."""
    entry = MockConfigEntry(domain="dyson_infrared", data=data)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id) is False

    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert entry.error_reason_translation_key == "unknown_device_type"
