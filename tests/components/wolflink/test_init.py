"""Test the Wolf SmartSet Service."""

from unittest.mock import patch

from httpx import RequestError

from homeassistant.components.wolflink.const import DEVICE_ID, DOMAIN
from homeassistant.core import HomeAssistant

from .const import CONFIG

from tests.common import MockConfigEntry


async def test_unique_id_migration(hass: HomeAssistant) -> None:
    """Test already configured while creating entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, unique_id=CONFIG[DEVICE_ID], data=CONFIG
    )
    config_entry.add_to_hass(hass)

    assert config_entry.unique_id == 1234
    assert (
        hass.config_entries.async_entry_for_domain_unique_id(DOMAIN, 1234)
        is config_entry
    )
    assert hass.config_entries.async_entry_for_domain_unique_id(DOMAIN, "1234") is None

    with (
        patch(
            "homeassistant.components.wolflink.fetch_parameters",
            side_effect=RequestError("Unable to fetch parameters"),
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)

    assert config_entry.unique_id == "1234"
    assert (
        hass.config_entries.async_entry_for_domain_unique_id(DOMAIN, "1234")
        is config_entry
    )
    assert hass.config_entries.async_entry_for_domain_unique_id(DOMAIN, 1234) is None
