"""Test data update coordinator for Linear Garage Door."""

from unittest.mock import patch

from linear_garage_door.errors import InvalidLoginError

from homeassistant.components.linear_garage_door.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_invalid_password(
    hass: HomeAssistant,
) -> None:
    """Test invalid password."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "email": "test-email",
            "password": "test-password",
            "site_id": "test-site-id",
            "device_id": "test-uuid",
        },
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.linear_garage_door.coordinator.Linear.login",
        side_effect=InvalidLoginError(
            "Login provided is invalid, please check the email and password"
        ),
    ):
        assert not await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert entries
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert flows
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == "reauth"


async def test_invalid_login(
    hass: HomeAssistant,
) -> None:
    """Test invalid login."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "email": "test-email",
            "password": "test-password",
            "site_id": "test-site-id",
            "device_id": "test-uuid",
        },
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.linear_garage_door.coordinator.Linear.login",
        side_effect=InvalidLoginError("Some other error"),
    ):
        assert not await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert entries
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.SETUP_RETRY
