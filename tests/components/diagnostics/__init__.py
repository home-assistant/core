"""Tests for the Diagnostics integration."""
from http import HTTPStatus

from homeassistant.setup import async_setup_component


async def _get_diagnostics_for_config_entry(hass, hass_client, config_entry):
    """Return the diagnostics config entry for the specified domain."""
    assert await async_setup_component(hass, "diagnostics", {})

    client = await hass_client()
    response = await client.get(
        f"/api/diagnostics/config_entry/{config_entry.entry_id}"
    )
    assert response.status == HTTPStatus.OK
    return await response.json()


async def get_diagnostics_for_config_entry(hass, hass_client, config_entry):
    """Return the diagnostics config entry for the specified domain."""
    data = await _get_diagnostics_for_config_entry(hass, hass_client, config_entry)
    return data["data"]


async def _get_diagnostics_for_device(hass, hass_client, config_entry, device):
    """Return the diagnostics for the specified device."""
    assert await async_setup_component(hass, "diagnostics", {})

    client = await hass_client()
    response = await client.get(
        f"/api/diagnostics/config_entry/{config_entry.entry_id}/device/{device.id}"
    )
    assert response.status == HTTPStatus.OK
    return await response.json()


async def get_diagnostics_for_device(hass, hass_client, config_entry, device):
    """Return the diagnostics for the specified device."""
    data = await _get_diagnostics_for_device(hass, hass_client, config_entry, device)
    return data["data"]
