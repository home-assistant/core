"""Fixtures for the Sensibo integration."""

from __future__ import annotations

from collections.abc import AsyncGenerator
import json
from typing import Any
from unittest.mock import patch

from pysensibo import SensiboClient
import pytest

from homeassistant.components.sensibo.const import DOMAIN, PLATFORMS
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from . import ENTRY_CONFIG

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture(name="load_platforms")
async def patch_platform_constant() -> list[Platform]:
    """Return list of platforms to load."""
    return PLATFORMS


@pytest.fixture
async def load_int(
    hass: HomeAssistant,
    mock_client: SensiboClient,
    load_platforms: list[Platform],
) -> MockConfigEntry:
    """Set up the Sensibo integration in Home Assistant."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data=ENTRY_CONFIG,
        entry_id="1",
        unique_id="username",
        version=2,
    )

    config_entry.add_to_hass(hass)

    with patch("homeassistant.components.sensibo.PLATFORMS", load_platforms):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    return config_entry


@pytest.fixture(name="mock_client")
async def get_client(
    hass: HomeAssistant,
    load_json: tuple[dict[str, Any], dict[str, Any]],
) -> AsyncGenerator[SensiboClient]:
    """Retrieve data from upstream Sensibo library."""

    with (
        patch(
            "homeassistant.components.sensibo.coordinator.SensiboClient",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.sensibo.util.SensiboClient",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.async_get_devices.return_value = load_json[0]
        client.async_get_me.return_value = load_json[1]
        yield client


@pytest.fixture(name="load_json")
def load_json_from_fixture(
    load_data: tuple[str, str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Load fixture with json data and return."""
    json_data: dict[str, Any] = json.loads(load_data[0])
    json_me: dict[str, Any] = json.loads(load_data[1])
    return (json_data, json_me)


@pytest.fixture(name="load_data", scope="package")
def load_data_from_fixture() -> tuple[str, str]:
    """Load fixture with fixture data and return."""
    return (load_fixture("data.json", "sensibo"), load_fixture("me.json", "sensibo"))
