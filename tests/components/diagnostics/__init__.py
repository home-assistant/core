"""Tests for the Diagnostics integration."""
from http import HTTPStatus

from homeassistant.helpers.device_registry import async_get
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def get_diagnostics_for_config_entry(hass, hass_client, domain_or_config_entry):
    """Return the diagnostics config entry for the specified domain."""
    if isinstance(domain_or_config_entry, str):
        config_entry = MockConfigEntry(domain=domain_or_config_entry)
        config_entry.add_to_hass(hass)
    else:
        config_entry = domain_or_config_entry

    assert await async_setup_component(hass, "diagnostics", {})

    client = await hass_client()
    response = await client.get(
        f"/api/diagnostics/config_entry/{config_entry.entry_id}"
    )
    assert response.status == HTTPStatus.OK
    return await response.json()


async def get_diagnostics_for_device(
    hass, hass_client, domain_or_config_entry, device_id=None
):
    """Return the diagnostics for the specified device."""
    if isinstance(domain_or_config_entry, str):
        config_entry = MockConfigEntry(domain=domain_or_config_entry)
        config_entry.add_to_hass(hass)
    else:
        config_entry = domain_or_config_entry

    dev_reg = async_get(hass)
    if isinstance(device_id, str):
        device = dev_reg.async_get(device_id)
    else:
        device = dev_reg.async_get_or_create(
            config_entry_id=config_entry.entry_id, identifiers={("test", "test")}
        )

    client = await hass_client()
    response = await client.get(
        f"/api/diagnostics/config_entry/{config_entry.entry_id}/device/{device.id}"
    )
    assert response.status == HTTPStatus.OK
    return await response.json()
