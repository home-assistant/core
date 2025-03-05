"""The tests for Evohome."""

from __future__ import annotations

from typing import Final
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.evohome.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .conftest import mock_make_request, mock_post_request

from tests.common import MockConfigEntry

_EXPECTED_CONFIG_ENTRY_DATA: Final = {
    "username": "test_user@gmail.com",
    "password": "P@ssw0rd",
    "location_idx": 0,
    "token_data": {
        "access_token_expires": "2024-07-10T12:30:00+00:00",
        "access_token": "new_at_1dc7z657UKzbhKA...",
        "refresh_token": "new_rf_jg68ZCKYdxEI3fF...",
    },
}

_EXPECTED_CONFIG_ENTRY_OPTIONS: Final = {"high_precision": True, "scan_interval": 300}


async def test_import_and_unload_entry(
    hass: HomeAssistant,
    config: dict[str, str],
    install: str,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test import of configuration and unload config entry."""

    freezer.move_to("2024-07-10T12:00:00+00:00")

    with (
        patch(
            "evohomeasync2.auth.CredentialsManagerBase._post_request",
            mock_post_request(install),
        ),
        patch(
            "evohome.auth.AbstractAuth._make_request",
            mock_make_request(install),
        ),
    ):
        result = await async_setup_component(hass, DOMAIN, {DOMAIN: config})
        await hass.async_block_till_done()  # wait for async_setup_entry()

    assert result is True
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]

    assert config_entry.state == ConfigEntryState.LOADED
    assert config_entry.source == SOURCE_IMPORT

    assert config_entry.data == _EXPECTED_CONFIG_ENTRY_DATA
    assert config_entry.options == _EXPECTED_CONFIG_ENTRY_OPTIONS
    assert config_entry.runtime_data["coordinator"] is not None

    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.NOT_LOADED  # type: ignore[comparison-overlap]


async def test_load_and_unload_entry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    install: str,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test load and unload config entry."""

    freezer.move_to("2024-07-10T12:00:00+00:00")

    config_entry.add_to_hass(hass)

    with (
        patch(
            "evohomeasync2.auth.CredentialsManagerBase._post_request",
            mock_post_request(install),
        ),
        patch(
            "evohome.auth.AbstractAuth._make_request",
            mock_make_request(install),
        ),
    ):
        result = await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert result is True
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    assert config_entry.state == ConfigEntryState.LOADED
    assert config_entry.source == SOURCE_USER

    assert config_entry.data == _EXPECTED_CONFIG_ENTRY_DATA
    assert config_entry.options == _EXPECTED_CONFIG_ENTRY_OPTIONS
    assert config_entry.runtime_data["coordinator"] is not None

    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.NOT_LOADED  # type: ignore[comparison-overlap]
