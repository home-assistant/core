"""Test Velbus diagnostics."""

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.components.diagnostics import REDACTED
from homeassistant.components.velbus.const import DOMAIN
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_PORT
from homeassistant.core import HomeAssistant

from . import init_integration


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    await init_integration(hass, config_entry)

    result = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)

    assert result == snapshot(exclude=props("created_at", "modified_at", "entry_id"))


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "controller")
async def test_manager_diagnostics_redact_access_token(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test config entry diagnostics redact manager access tokens."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_PORT: "manager://127.0.0.1:4201",
            CONF_ACCESS_TOKEN: "secret-token",
        },
    )
    entry.add_to_hass(hass)
    await init_integration(hass, entry)

    result = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    assert result["entry"]["data"][CONF_ACCESS_TOKEN] == REDACTED
