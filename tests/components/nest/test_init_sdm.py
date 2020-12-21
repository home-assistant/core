"""
Test for setup methods for the SDM API.

The tests fake out the subscriber/devicemanager and simulate setup behavior
and failure modes.
"""

from google_nest_sdm.exceptions import GoogleNestException

from homeassistant.components.nest import DOMAIN
from homeassistant.config_entries import (
    ENTRY_STATE_LOADED,
    ENTRY_STATE_SETUP_ERROR,
    ENTRY_STATE_SETUP_RETRY,
)
from homeassistant.setup import async_setup_component

from .common import CONFIG, CONFIG_ENTRY_DATA, async_setup_sdm_platform

from tests.async_mock import patch
from tests.common import MockConfigEntry

PLATFORM = "sensor"


async def test_setup_success(hass):
    """Test successful setup."""
    await async_setup_component(hass, "persistent_notification", {})
    await async_setup_sdm_platform(hass, PLATFORM)

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state == ENTRY_STATE_LOADED

    state = hass.states.get("persistent_notification.nest_setup")
    assert state is None


async def async_setup_sdm(hass, config=CONFIG):
    """Prepare test setup."""
    MockConfigEntry(domain=DOMAIN, data=CONFIG_ENTRY_DATA).add_to_hass(hass)
    with patch(
        "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation"
    ):
        await async_setup_component(hass, DOMAIN, config)


async def test_setup_configuration_failure(hass):
    """Test configuration error."""
    await async_setup_component(hass, "persistent_notification", {})

    config = CONFIG.copy()
    config[DOMAIN]["subscriber_id"] = "invalid-subscriber-format"

    await async_setup_sdm(hass, config)

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state == ENTRY_STATE_SETUP_ERROR

    state = hass.states.get("persistent_notification.nest_setup")
    assert state is not None
    # This error comes from the python google-nest-sdm library, as a check added
    # to prevent common misconfigurations (e.g. confusing topic and subscriber)
    assert state.attributes["title"] == "Nest configuration error"
    assert (
        "Subscription misconfigured. Expected subscriber_id"
        in state.attributes["message"]
    )


async def test_setup_susbcriber_failure(hass):
    """Test configuration error."""
    await async_setup_component(hass, "persistent_notification", {})

    state = hass.states.get("persistent_notification.nest_setup")
    assert state is None

    with patch(
        "homeassistant.components.nest.GoogleNestSubscriber.start_async",
        side_effect=GoogleNestException(),
    ):
        await async_setup_sdm(hass)

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state == ENTRY_STATE_SETUP_RETRY

    state = hass.states.get("persistent_notification.nest_setup")
    assert state is not None
    assert state.attributes["title"] == "Nest unavailable"
    assert state.attributes["message"] == "Subscriber error:"


async def test_setup_device_manager_failure(hass):
    """Test configuration error."""
    await async_setup_component(hass, "persistent_notification", {})

    state = hass.states.get("persistent_notification.nest_setup")
    assert state is None

    with patch("homeassistant.components.nest.GoogleNestSubscriber.start_async"), patch(
        "homeassistant.components.nest.GoogleNestSubscriber.async_get_device_manager",
        side_effect=GoogleNestException(),
    ):
        await async_setup_sdm(hass)
        await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state == ENTRY_STATE_SETUP_RETRY

    state = hass.states.get("persistent_notification.nest_setup")
    assert state is not None
    assert state.attributes["title"] == "Nest unavailable"
    assert state.attributes["message"] == "Device manager error:"
