"""Tests for the Diagnostics integration."""
from http import HTTPStatus

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
