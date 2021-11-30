"""Test the init functions for AEH."""
from unittest.mock import patch

from azure.eventhub.exceptions import EventHubError

from homeassistant.components import azure_event_hub
from homeassistant.setup import async_setup_component

from .const import (
    BASIC_OPTIONS,
    CS_CONFIG_FULL,
    PRODUCER_PATH,
    SAS_CONFIG_FULL,
    UPDATE_OPTIONS,
)

from tests.common import MockConfigEntry


async def test_import(hass):
    """Test the popping of the filter and further import of the config."""
    config = {
        azure_event_hub.DOMAIN: {
            "send_interval": 10,
            "max_delay": 10,
            "filter": {
                "include_domains": ["light"],
                "include_entity_globs": ["sensor.included_*"],
                "include_entities": ["binary_sensor.included"],
                "exclude_domains": ["light"],
                "exclude_entity_globs": ["sensor.excluded_*"],
                "exclude_entities": ["binary_sensor.excluded"],
            },
        }
    }
    config[azure_event_hub.DOMAIN].update(CS_CONFIG_FULL)
    assert await async_setup_component(hass, azure_event_hub.DOMAIN, config)


async def test_filter_only_config(hass):
    """Test the popping of the filter and further import of the config."""
    config = {
        azure_event_hub.DOMAIN: {
            "filter": {
                "include_domains": ["light"],
                "include_entity_globs": ["sensor.included_*"],
                "include_entities": ["binary_sensor.included"],
                "exclude_domains": ["light"],
                "exclude_entity_globs": ["sensor.excluded_*"],
                "exclude_entities": ["binary_sensor.excluded"],
            },
        }
    }
    assert await async_setup_component(hass, azure_event_hub.DOMAIN, config)


async def test_setup(hass, mock_hub):
    """Test the async_setup function."""
    entry = MockConfigEntry(
        domain=azure_event_hub.DOMAIN,
        data=SAS_CONFIG_FULL,
        title="test-instance",
        options=BASIC_OPTIONS,
    )
    entry.add_to_hass(hass)
    assert await azure_event_hub.async_setup_entry(hass, entry)
    assert hass.data[azure_event_hub.DOMAIN]["hub"] is not None
    assert isinstance(
        hass.data[azure_event_hub.DOMAIN]["hub"], azure_event_hub.hub.AzureEventHub
    )


async def test_unload_entry(hass, mock_hub):
    """Test being able to unload an entry."""
    entry = MockConfigEntry(
        domain=azure_event_hub.DOMAIN,
        data=SAS_CONFIG_FULL,
        title="test-instance",
        options=BASIC_OPTIONS,
    )
    entry.add_to_hass(hass)
    assert await azure_event_hub.async_setup_entry(hass, entry)
    assert hass.data[azure_event_hub.DOMAIN].get("hub") is not None
    assert await azure_event_hub.async_unload_entry(hass, entry)
    assert hass.data[azure_event_hub.DOMAIN].get("hub") is None


async def test_failed_test_connection(hass):
    """Test being able to unload an entry."""
    entry = MockConfigEntry(
        domain=azure_event_hub.DOMAIN,
        data=SAS_CONFIG_FULL,
        title="test-instance",
        options=BASIC_OPTIONS,
    )
    entry.add_to_hass(hass)
    with patch(
        f"{PRODUCER_PATH}.get_eventhub_properties",
        side_effect=EventHubError("test"),
    ):
        try:
            await azure_event_hub.async_setup_entry(hass, entry)
        except azure_event_hub.ConfigEntryNotReady:
            pass
        assert hass.data[azure_event_hub.DOMAIN].get("hub") is None


async def test_update_listener(hass, mock_hub):
    """Test being able to update options."""
    entry = MockConfigEntry(
        domain=azure_event_hub.DOMAIN,
        data=SAS_CONFIG_FULL,
        title="test-instance",
        options=BASIC_OPTIONS,
    )
    entry.add_to_hass(hass)
    assert await azure_event_hub.async_setup_entry(hass, entry)
    entry.options = UPDATE_OPTIONS
    await azure_event_hub.async_update_listener(hass, entry)
    assert hass.data[azure_event_hub.DOMAIN]["hub"].update_options.call_count == 1
    hass.data[azure_event_hub.DOMAIN]["hub"].update_options.assert_called_with(
        UPDATE_OPTIONS
    )
