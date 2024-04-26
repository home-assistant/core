"""Test Enphase Envoy diagnostics."""

from unittest.mock import AsyncMock, patch

from pyenphase.exceptions import EnvoyError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.enphase_envoy.const import (
    DOMAIN,
    OPTION_DIAGNOSTICS_INCLUDE_FIXTURES,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator

# Fields to exclude from snapshot as they change each run
TO_EXCLUDE = {
    "id",
    "device_id",
    "via_device_id",
    "last_updated",
    "last_changed",
    "last_reported",
}


def limit_diagnostic_attrs(prop, path) -> bool:
    """Mark attributes to exclude from diagnostic snapshot."""
    return prop in TO_EXCLUDE


async def test_entry_diagnostics(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    hass_client: ClientSessionGenerator,
    setup_enphase_envoy,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    assert await get_diagnostics_for_config_entry(
        hass, hass_client, config_entry
    ) == snapshot(exclude=limit_diagnostic_attrs)


@pytest.fixture(name="config_entry_options")
def config_entry_options_fixture(hass: HomeAssistant, config, serial_number):
    """Define a config entry fixture."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="45a36e55aaddb2007c5f6602e0c38e72",
        title=f"Envoy {serial_number}" if serial_number else "Envoy",
        unique_id=serial_number,
        data=config,
        options={OPTION_DIAGNOSTICS_INCLUDE_FIXTURES: True},
    )
    entry.add_to_hass(hass)
    return entry


async def test_entry_diagnostics_with_fixtures(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry_options: ConfigEntry,
    setup_enphase_envoy,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    assert await get_diagnostics_for_config_entry(
        hass, hass_client, config_entry_options
    ) == snapshot(exclude=limit_diagnostic_attrs)


@pytest.fixture(name="setup_enphase_envoy_options_error")
async def setup_enphase_envoy_options_error_fixture(
    hass: HomeAssistant,
    config,
    mock_envoy_options_error,
):
    """Define a fixture to set up Enphase Envoy."""
    with (
        patch(
            "homeassistant.components.enphase_envoy.config_flow.Envoy",
            return_value=mock_envoy_options_error,
        ),
        patch(
            "homeassistant.components.enphase_envoy.Envoy",
            return_value=mock_envoy_options_error,
        ),
    ):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
        yield


@pytest.fixture(name="mock_envoy_options_error")
def mock_envoy_options_fixture(
    mock_envoy,
):
    """Mock envoy with error in request."""
    mock_envoy_options = mock_envoy
    mock_envoy_options.request.side_effect = AsyncMock(side_effect=EnvoyError("Test"))
    return mock_envoy_options


async def test_entry_diagnostics_with_fixtures_with_error(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry_options: ConfigEntry,
    setup_enphase_envoy_options_error,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    assert await get_diagnostics_for_config_entry(
        hass, hass_client, config_entry_options
    ) == snapshot(exclude=limit_diagnostic_attrs)
