"""Tests for the Airgradient integration."""

from airgradient import (
    ApiVersion,
    Config,
    Measures,
    parse_config_json,
    parse_measures_json,
)

from homeassistant.components.airgradient.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_load_fixture, load_fixture


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Fixture for setting up the component."""
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


def load_measures_fixture(
    filename: str, api_version: ApiVersion = ApiVersion.LEGACY
) -> Measures:
    """Load and parse a measures fixture."""
    return parse_measures_json(load_fixture(filename, DOMAIN), api_version=api_version)


def load_config_fixture(
    filename: str, api_version: ApiVersion = ApiVersion.LEGACY
) -> Config:
    """Load and parse a config fixture."""
    return parse_config_json(load_fixture(filename, DOMAIN), api_version=api_version)


async def async_load_measures_fixture(
    hass: HomeAssistant,
    filename: str,
    api_version: ApiVersion = ApiVersion.LEGACY,
) -> Measures:
    """Load and parse a measures fixture asynchronously."""
    return parse_measures_json(
        await async_load_fixture(hass, filename, DOMAIN),
        api_version=api_version,
    )


async def async_load_config_fixture(
    hass: HomeAssistant,
    filename: str,
    api_version: ApiVersion = ApiVersion.LEGACY,
) -> Config:
    """Load and parse a config fixture asynchronously."""
    return parse_config_json(
        await async_load_fixture(hass, filename, DOMAIN),
        api_version=api_version,
    )
