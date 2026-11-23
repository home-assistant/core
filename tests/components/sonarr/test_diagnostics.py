"""Tests for the Sonarr diagnostics."""

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.sonarr.const import DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, init_integration)
        == snapshot
    )


@pytest.mark.parametrize(
    "url",
    [
        pytest.param(
            "https://user:secret-password@sonarr.example.com:443/",
            id="user_and_password",
        ),
        pytest.param(
            "https://:secret-token@sonarr.example.com:443/", id="password_only"
        ),
    ],
)
@pytest.mark.usefixtures("mock_sonarr")
async def test_entry_diagnostics_url_credentials(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
    url: str,
) -> None:
    """Test config entry diagnostics redact credentials in the URL."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        data={
            CONF_URL: url,
            CONF_API_KEY: "MOCK_API_KEY",
            CONF_VERIFY_SSL: True,
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert await get_diagnostics_for_config_entry(hass, hass_client, entry) == snapshot
