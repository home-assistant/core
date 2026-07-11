"""Tests for the Steam integration."""

from unittest.mock import MagicMock

import pytest
import steam.api
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.steam_online.const import (
    CONF_ACCOUNTS,
    DOMAIN,
    SUBENTRY_TYPE_FRIEND,
)
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import ACCOUNT_1, ACCOUNT_2, ACCOUNT_NAME_1, ACCOUNT_NAME_2, CONF_DATA

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
    side_effect: type[Exception],
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
    side_effect: type[Exception],
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
    snapshot: SnapshotAssertion,
) -> None:
    """Test device info."""
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert (
        device_registry.async_get_device(identifiers={(DOMAIN, ACCOUNT_1)}) == snapshot
    )


@pytest.mark.usefixtures("steam_api")
async def test_migrate_entry(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test entry migration."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONF_DATA,
        options={
            CONF_ACCOUNTS: {
                ACCOUNT_1: ACCOUNT_NAME_1,
                ACCOUNT_2: ACCOUNT_NAME_2,
            }
        },
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

    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, config_entry.entry_id)},
    )

    assert sensor.unique_id == f"sensor.steam_{ACCOUNT_1}"

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.version == 3

    assert (sensor := entity_registry.async_get(sensor.entity_id))
    assert sensor.unique_id == f"{ACCOUNT_1}_account"

    assert (device := device_registry.async_get(device.id))
    assert device.identifiers == {(DOMAIN, ACCOUNT_1)}

    assert len(config_entry.subentries) == 1
    subentries = list(config_entry.subentries.values())
    assert subentries[0].unique_id == ACCOUNT_2
    assert subentries[0].title == ACCOUNT_NAME_2
    assert subentries[0].subentry_type == SUBENTRY_TYPE_FRIEND

    assert config_entry.options == {}

    assert device_registry.async_get_device(identifiers={(DOMAIN, ACCOUNT_2)})
