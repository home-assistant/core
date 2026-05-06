"""Tests for the SVS Subwoofer services."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.svs_subwoofer.const import (
    DOMAIN,
    SERVICE_LOAD_PRESET,
    SERVICE_SET_VOLUME,
    SERVICE_SYNC_FROM,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr

from . import SVS_ADDRESS, async_init_integration


async def _device_id_for(hass: HomeAssistant, address: str) -> str:
    """Return the device registry ID for a configured subwoofer."""
    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, address)})
    assert device is not None
    return device.id


async def test_set_volume(hass: HomeAssistant, mock_bleak_client: MagicMock) -> None:
    """`set_volume` writes a single VOLUME frame to the target subwoofer."""
    await async_init_integration(hass)
    device_id = await _device_id_for(hass, SVS_ADDRESS)

    pre = mock_bleak_client.write_gatt_char.await_count
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_VOLUME,
        {"device_ids": [device_id], "volume": -25},
        blocking=True,
    )
    assert mock_bleak_client.write_gatt_char.await_count == pre + 1


async def test_set_volume_unknown_device(
    hass: HomeAssistant, mock_bleak_client: MagicMock
) -> None:
    """An unknown device_id raises ServiceValidationError."""
    await async_init_integration(hass)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_VOLUME,
            {"device_ids": ["does-not-exist"], "volume": -25},
            blocking=True,
        )


async def test_load_preset_string(
    hass: HomeAssistant, mock_bleak_client: MagicMock
) -> None:
    """`load_preset` accepts a string preset id and dispatches a PRESETLOAD frame."""
    await async_init_integration(hass)
    device_id = await _device_id_for(hass, SVS_ADDRESS)

    pre = mock_bleak_client.write_gatt_char.await_count
    await hass.services.async_call(
        DOMAIN,
        SERVICE_LOAD_PRESET,
        {"device_ids": [device_id], "preset": "2"},
        blocking=True,
    )
    # Preset load frame + 4 follow-up MEMREAD frames
    assert mock_bleak_client.write_gatt_char.await_count >= pre + 5


async def test_sync_from_unknown_source(
    hass: HomeAssistant, mock_bleak_client: MagicMock
) -> None:
    """`sync_from` with an unknown source device raises ServiceValidationError."""
    await async_init_integration(hass)
    target_id = await _device_id_for(hass, SVS_ADDRESS)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SYNC_FROM,
            {"source_device_id": "missing", "target_device_ids": [target_id]},
            blocking=True,
        )


async def test_sync_from_skips_none_values(
    hass: HomeAssistant, mock_bleak_client: MagicMock
) -> None:
    """`sync_from` does not send writes for parameters the source has not seen."""
    # Set up two subwoofers
    entry = await async_init_integration(hass)
    entry2 = await async_init_integration(
        hass, address="08:EB:ED:AA:BB:CC", name="LEFTSUB"
    )
    source_id = await _device_id_for(hass, SVS_ADDRESS)
    target_id = await _device_id_for(hass, "08:EB:ED:AA:BB:CC")

    # Source coordinator has no validated values yet (data == {}),
    # so sync_from should be a no-op.
    pre = mock_bleak_client.write_gatt_char.await_count
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SYNC_FROM,
        {"source_device_id": source_id, "target_device_ids": [target_id]},
        blocking=True,
    )
    assert mock_bleak_client.write_gatt_char.await_count == pre

    # Pin a single value on the source and re-run; a single write is expected.
    entry.runtime_data.data["VOLUME"] = -25
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SYNC_FROM,
        {"source_device_id": source_id, "target_device_ids": [target_id]},
        blocking=True,
    )
    assert mock_bleak_client.write_gatt_char.await_count == pre + 1
    _ = entry2  # silence unused-variable lint
