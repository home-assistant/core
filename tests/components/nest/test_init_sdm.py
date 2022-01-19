"""
Test for setup methods for the SDM API.

The tests fake out the subscriber/devicemanager and simulate setup behavior
and failure modes.
"""

import copy
import logging
from unittest.mock import patch

from google_nest_sdm.exceptions import (
    ApiException,
    AuthException,
    ConfigurationException,
    SubscriberException,
)

from homeassistant.components.nest import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.setup import async_setup_component

from .common import CONFIG, async_setup_sdm_platform, create_config_entry

PLATFORM = "sensor"


async def test_setup_success(hass, caplog):
    """Test successful setup."""
    with caplog.at_level(logging.ERROR, logger="homeassistant.components.nest"):
        await async_setup_sdm_platform(hass, PLATFORM)
        assert not caplog.records

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.LOADED


async def async_setup_sdm(hass, config=CONFIG, with_config=True):
    """Prepare test setup."""
    if with_config:
        create_config_entry(hass)
    with patch(
        "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation"
    ):
        return await async_setup_component(hass, DOMAIN, config)


async def test_setup_configuration_failure(hass, caplog):
    """Test configuration error."""
    config = copy.deepcopy(CONFIG)
    config[DOMAIN]["subscriber_id"] = "invalid-subscriber-format"

    result = await async_setup_sdm(hass, config)
    assert result

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.SETUP_ERROR

    # This error comes from the python google-nest-sdm library, as a check added
    # to prevent common misconfigurations (e.g. confusing topic and subscriber)
    assert "Subscription misconfigured. Expected subscriber_id" in caplog.text


async def test_setup_susbcriber_failure(hass, caplog):
    """Test configuration error."""
    with patch(
        "homeassistant.components.nest.api.GoogleNestSubscriber.start_async",
        side_effect=SubscriberException(),
    ), caplog.at_level(logging.ERROR, logger="homeassistant.components.nest"):
        result = await async_setup_sdm(hass)
        assert result
        assert "Subscriber error:" in caplog.text

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.SETUP_RETRY


async def test_setup_device_manager_failure(hass, caplog):
    """Test configuration error."""
    with patch(
        "homeassistant.components.nest.api.GoogleNestSubscriber.start_async"
    ), patch(
        "homeassistant.components.nest.api.GoogleNestSubscriber.async_get_device_manager",
        side_effect=ApiException(),
    ), caplog.at_level(
        logging.ERROR, logger="homeassistant.components.nest"
    ):
        result = await async_setup_sdm(hass)
        assert result
        assert len(caplog.messages) == 1
        assert "Device manager error:" in caplog.text

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.SETUP_RETRY


async def test_subscriber_auth_failure(hass, caplog):
    """Test configuration error."""
    with patch(
        "homeassistant.components.nest.api.GoogleNestSubscriber.start_async",
        side_effect=AuthException(),
    ):
        result = await async_setup_sdm(hass, CONFIG)
        assert result

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"


async def test_setup_missing_subscriber_id(hass, caplog):
    """Test missing susbcriber id from config and config entry."""
    config = copy.deepcopy(CONFIG)
    del config[DOMAIN]["subscriber_id"]

    with caplog.at_level(logging.WARNING, logger="homeassistant.components.nest"):
        result = await async_setup_sdm(hass, config)
        assert result
        assert "Configuration option" in caplog.text

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.SETUP_ERROR


async def test_setup_subscriber_id_config_entry(hass, caplog):
    """Test successful setup with subscriber id in ConfigEntry."""
    config = copy.deepcopy(CONFIG)
    subscriber_id = config[DOMAIN]["subscriber_id"]
    del config[DOMAIN]["subscriber_id"]

    config_entry = create_config_entry(hass)
    data = {**config_entry.data}
    data["subscriber_id"] = subscriber_id
    hass.config_entries.async_update_entry(config_entry, data=data)

    with caplog.at_level(logging.ERROR, logger="homeassistant.components.nest"):
        await async_setup_sdm_platform(hass, PLATFORM, with_config=False)
        assert not caplog.records

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.LOADED


async def test_subscriber_configuration_failure(hass, caplog):
    """Test configuration error."""
    with patch(
        "homeassistant.components.nest.api.GoogleNestSubscriber.start_async",
        side_effect=ConfigurationException(),
    ), caplog.at_level(logging.ERROR, logger="homeassistant.components.nest"):
        result = await async_setup_sdm(hass, CONFIG)
        assert result
        assert "Configuration error: " in caplog.text

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.SETUP_ERROR


async def test_empty_config(hass, caplog):
    """Test successful setup."""
    with caplog.at_level(logging.ERROR, logger="homeassistant.components.nest"):
        result = await async_setup_component(hass, DOMAIN, {})
        assert result
        assert not caplog.records

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 0


async def test_unload_entry(hass, caplog):
    """Test successful unload of a ConfigEntry."""
    await async_setup_sdm_platform(hass, PLATFORM)

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state == ConfigEntryState.NOT_LOADED


async def test_remove_entry(hass, caplog):
    """Test successful unload of a ConfigEntry."""
    await async_setup_sdm_platform(hass, PLATFORM)

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_remove(entry.entry_id)

    entries = hass.config_entries.async_entries(DOMAIN)
    assert not entries


async def test_remove_entry_deletes_subscriber(hass, caplog):
    """Test ConfigEntry unload deletes a subscription."""
    config = copy.deepcopy(CONFIG)
    subscriber_id = config[DOMAIN]["subscriber_id"]
    del config[DOMAIN]["subscriber_id"]

    config_entry = create_config_entry(hass)
    data = {**config_entry.data}
    data["subscriber_id"] = subscriber_id
    hass.config_entries.async_update_entry(config_entry, data=data)

    await async_setup_sdm_platform(hass, PLATFORM, with_config=False)

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.state is ConfigEntryState.LOADED

    with patch(
        "homeassistant.components.nest.api.GoogleNestSubscriber.delete_subscription",
    ) as delete:
        assert await hass.config_entries.async_remove(entry.entry_id)
        assert delete.called

    entries = hass.config_entries.async_entries(DOMAIN)
    assert not entries


async def test_remove_entry_delete_subscriber_failure(hass, caplog):
    """Test a failure when deleting the subscription."""
    config = copy.deepcopy(CONFIG)
    subscriber_id = config[DOMAIN]["subscriber_id"]
    del config[DOMAIN]["subscriber_id"]

    config_entry = create_config_entry(hass)
    data = {**config_entry.data}
    data["subscriber_id"] = subscriber_id
    hass.config_entries.async_update_entry(config_entry, data=data)

    await async_setup_sdm_platform(hass, PLATFORM, with_config=False)

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.state is ConfigEntryState.LOADED

    with patch(
        "homeassistant.components.nest.api.GoogleNestSubscriber.delete_subscription",
        side_effect=SubscriberException(),
    ):
        assert await hass.config_entries.async_remove(entry.entry_id)

    entries = hass.config_entries.async_entries(DOMAIN)
    assert not entries
