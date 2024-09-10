"""Test the Wolf SmartSet Service config flow."""

from unittest.mock import patch

from httpx import RequestError
from wolf_comm.models import Device

from homeassistant.components.wolflink.const import (
    DEVICE_GATEWAY,
    DEVICE_ID,
    DEVICE_NAME,
    DOMAIN,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

CONFIG = {
    DEVICE_NAME: "test-device",
    DEVICE_ID: 1234,
    DEVICE_GATEWAY: 5678,
    CONF_USERNAME: "test-username",
    CONF_PASSWORD: "test-password",
}

DEVICE = Device(CONFIG[DEVICE_ID], CONFIG[DEVICE_GATEWAY], CONFIG[DEVICE_NAME])


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
