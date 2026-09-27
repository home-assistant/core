"""Test the Whirlpool Sixth Sense init."""

import logging
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest
from whirlpool.auth import AccountLockedError
from whirlpool.backendselector import Brand, Region

from homeassistant.components.whirlpool.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_REGION,
    CONF_USERNAME,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration, init_integration_with_entry, trigger_attr_callback

from tests.common import MockConfigEntry


async def test_setup(
    hass: HomeAssistant,
    mock_backend_selector_api: MagicMock,
    region,
    brand,
) -> None:
    """Test setup."""
    entry = await init_integration(hass, region[0], brand[0])
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state is ConfigEntryState.LOADED
    mock_backend_selector_api.assert_called_once_with(brand[1], region[1])


async def test_setup_region_fallback(
    hass: HomeAssistant,
    mock_backend_selector_api: MagicMock,
) -> None:
    """Test setup when no region is available on the ConfigEntry.

    This can happen after a version update, since there was no region
    in the first versions.
    """

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: "nobody",
            CONF_PASSWORD: "qwerty",
        },
    )
    entry = await init_integration_with_entry(hass, entry)
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state is ConfigEntryState.LOADED
    mock_backend_selector_api.assert_called_once_with(Brand.Whirlpool, Region.EU)


async def test_setup_brand_fallback(
    hass: HomeAssistant,
    region,
    mock_backend_selector_api: MagicMock,
) -> None:
    """Test setup when no brand is available on the ConfigEntry.

    This can happen after a version update, since the brand was not
    selected or stored in the earlier versions.
    """

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: "nobody",
            CONF_PASSWORD: "qwerty",
            CONF_REGION: region[0],
        },
    )
    entry = await init_integration_with_entry(hass, entry)
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state is ConfigEntryState.LOADED
    mock_backend_selector_api.assert_called_once_with(Brand.Whirlpool, region[1])


async def test_setup_no_appliances(
    hass: HomeAssistant, mock_appliances_manager_api: MagicMock
) -> None:
    """Test setup when there are no appliances available."""
    mock_appliances_manager_api.return_value.aircons = []
    mock_appliances_manager_api.return_value.washers = []
    mock_appliances_manager_api.return_value.dryers = []
    mock_appliances_manager_api.return_value.ovens = []
    mock_appliances_manager_api.return_value.refrigerators = []

    await init_integration(hass)
    assert len(hass.states.async_all()) == 0


@pytest.mark.parametrize(
    ("exception", "expected_entry_state"),
    [
        (aiohttp.ClientConnectionError(), ConfigEntryState.SETUP_RETRY),
        (AccountLockedError, ConfigEntryState.SETUP_ERROR),
    ],
)
async def test_setup_auth_exception(
    hass: HomeAssistant,
    mock_auth_api: MagicMock,
    exception: Exception,
    expected_entry_state: ConfigEntryState,
) -> None:
    """Test setup with an exception during authentication."""
    mock_auth_api.return_value.do_auth.side_effect = exception
    entry = await init_integration(hass)
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state is expected_entry_state


async def test_setup_auth_failed(
    hass: HomeAssistant,
    mock_auth_api: MagicMock,
) -> None:
    """Test setup with failed auth."""
    mock_auth_api.return_value.do_auth = AsyncMock()
    mock_auth_api.return_value.is_access_token_valid.return_value = False
    entry = await init_integration(hass)
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_connect_failed(
    hass: HomeAssistant, mock_appliances_manager_api: MagicMock
) -> None:
    """Test setup with failed connect call."""
    mock_appliances_manager_api.return_value.connect = AsyncMock(return_value=False)
    entry = await init_integration(hass)
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test successful unload of entry."""
    entry = await init_integration(hass)
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_availability_logs(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    entity_registry: er.EntityRegistry,
    mock_appliances_manager_api: MagicMock,
) -> None:
    """Test availability and transition logs for every appliance entity."""
    manager = mock_appliances_manager_api.return_value
    appliances = [
        *manager.aircons,
        *manager.washers,
        *manager.dryers,
        *manager.ovens,
        *manager.refrigerators,
    ]
    for appliance in appliances:
        appliance.get_online.return_value = False
    entry = await init_integration(hass)

    entity_ids = {
        entity.entity_id
        for entity in er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    }
    assert entity_ids
    for entity_id in entity_ids:
        assert (state := hass.states.get(entity_id)) is not None
        assert state.state == STATE_UNAVAILABLE

    # Repeated updates must not log again; subsequent transitions must log again.
    for online, message, log_count in (
        (True, "is back online", 1),
        (False, "is unavailable", 1),
        (False, "is unavailable", 0),
        (True, "is back online", 1),
        (True, "is back online", 0),
        (False, "is unavailable", 1),
    ):
        caplog.clear()
        for appliance in appliances:
            appliance.get_online.return_value = online
            await trigger_attr_callback(hass, appliance)

        for entity_id in entity_ids:
            assert (state := hass.states.get(entity_id)) is not None
            assert (state.state != STATE_UNAVAILABLE) is online
            assert (
                caplog.record_tuples.count(
                    (
                        "homeassistant.components.whirlpool.entity",
                        logging.INFO,
                        f"The entity {entity_id} {message}",
                    )
                )
                == log_count
            )
