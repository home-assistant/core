"""Tests for the Enphase Envoy integration."""

from datetime import timedelta

from jwt import encode

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.util.dt import now

from tests.common import MockConfigEntry


async def setup_integration(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    expected_state: ConfigEntryState = ConfigEntryState.LOADED,
) -> None:
    """Fixture for setting up the component and testing expected state."""
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert config_entry.state is expected_state


def envoy_token(days_to_expiry: int = 365) -> str:
    """Build envoy token with specified days to expiration."""
    return encode(
        payload={
            "name": "envoy",
            "exp": (now() + timedelta(days=days_to_expiry)).timestamp(),
        },
        key="secret",
        algorithm="HS256",
    )
