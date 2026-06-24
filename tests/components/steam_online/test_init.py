"""Tests for the Steam integration."""

from unittest.mock import MagicMock

import pytest
import steam.api

from homeassistant.components.steam_online.const import DEFAULT_NAME, DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import ACCOUNT_1, ACCOUNT_NAME_1, CONF_DATA, CONF_OPTIONS

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("steam_api")
async def test_setup(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test unload."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)


@pytest.mark.parametrize(
    "side_effect",
    [
        steam.api.HTTPError,
        steam.api.HTTPTimeoutError,
    ],
)
async def test_setup_errors(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    steam_api: MagicMock,
    side_effect: Exception,
) -> None:
    """Test setup errors."""
    config_entry.add_to_hass(hass)

    steam_api.return_value.GetPlayerSummaries.side_effect = side_effect

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    "side_effect",
    [
        steam.api.HTTPError("Server connection failed: Forbidden (403)"),
        steam.api.HTTPError("Server connection failed: Unauthorized (401)"),
    ],
)
async def test_setup_auth_failed(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    steam_api: MagicMock,
    side_effect: Exception,
) -> None:
    """Test that it throws ConfigEntryAuthFailed when authentication fails."""
    config_entry.add_to_hass(hass)

    steam_api.return_value.GetPlayerSummaries.side_effect = side_effect

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow.get("step_id") == "reauth_confirm"
    assert flow.get("handler") == DOMAIN

    assert "context" in flow
    assert flow["context"].get("source") == SOURCE_REAUTH
    assert flow["context"].get("entry_id") == config_entry.entry_id


@pytest.mark.usefixtures("steam_api")
async def test_device_info(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
) -> None:
    """Test device info."""
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert (
        device := device_registry.async_get_device(
            identifiers={(DOMAIN, config_entry.entry_id)}
        )
    )

    assert device.configuration_url == "https://store.steampowered.com"
    assert device.entry_type == dr.DeviceEntryType.SERVICE
    assert device.identifiers == {(DOMAIN, config_entry.entry_id)}
    assert device.manufacturer == DEFAULT_NAME
    assert device.name == DEFAULT_NAME


@pytest.mark.usefixtures("steam_api")
async def test_migrate_entry(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test entry migration."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONF_DATA,
        options=CONF_OPTIONS,
        unique_id=ACCOUNT_1,
        version=1,
    )

    config_entry.add_to_hass(hass)

    assert config_entry.version == 1

    sensor = entity_registry.async_get_or_create(
        domain=Platform.SENSOR,
        platform=DOMAIN,
        unique_id=f"sensor.steam_{ACCOUNT_1}",
        config_entry=config_entry,
        original_name=ACCOUNT_NAME_1,
    )

    assert sensor.unique_id == f"sensor.steam_{ACCOUNT_1}"

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.version == 2

    assert (sensor := entity_registry.async_get(sensor.entity_id))
    assert sensor.unique_id == f"{ACCOUNT_1}_account"
