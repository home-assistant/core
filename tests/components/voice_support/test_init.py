"""Test setting up the Voice app."""

from collections.abc import Callable
from datetime import timedelta

import aiohttp
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.labs import async_update_preview_feature
from homeassistant.components.voice_support import async_get_client
from homeassistant.components.voice_support.const import (
    API_VERSION,
    DOMAIN,
    INFO_INTERVAL_MINUTES,
    PREVIEW_FEATURE_WAKE_WORD_VERIFICATION,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import FakeApp

pytestmark = pytest.mark.usefixtures("socket_enabled")


async def test_setup_registers_the_provider(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """Test the app becomes the pipeline's wake word client."""
    client = async_get_client(hass)
    assert client is not None
    assert client.supports_wake_word("okay nabu")
    assert client.supports_wake_word("Okay Nabu")
    assert not client.supports_wake_word("hey_jarvis")


async def test_unload_takes_the_provider_away(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """Test the pipeline stops asking when the app goes."""
    assert await hass.config_entries.async_unload(setup_integration.entry_id)
    await hass.async_block_till_done()

    assert async_get_client(hass) is None


async def test_an_app_that_is_not_answering_is_retried(
    hass: HomeAssistant,
    fake_app: FakeApp,
    config_entry_for: Callable[[FakeApp], MockConfigEntry],
) -> None:
    """Test setup is retried rather than failed when the app is not up."""
    entry = config_entry_for(fake_app)
    await fake_app.stop()
    entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("verification_enabled")
async def test_an_app_from_the_future_verifies_nothing(
    hass: HomeAssistant,
    fake_app: FakeApp,
    config_entry_for: Callable[[FakeApp], MockConfigEntry],
) -> None:
    """Test a protocol version this does not know is left alone."""
    fake_app.info["api_version"] = API_VERSION + 1
    entry = config_entry_for(fake_app)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    client = async_get_client(hass)
    assert client is not None
    assert not client.supports_wake_word("okay nabu")


async def test_the_app_going_quiet_is_not_fatal(
    hass: HomeAssistant,
    fake_app: FakeApp,
    setup_integration: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an app that stops answering stops being available.

    Satellites are asked for wake word audio because something will check
    it, so an app that has gone has to be noticed rather than discovered at
    the next detection.
    """
    client = setup_integration.runtime_data
    changes: list[bool] = []
    client.async_add_listener(lambda: changes.append(client.available))

    await fake_app.stop()
    freezer.tick(timedelta(minutes=INFO_INTERVAL_MINUTES + 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert changes == [False]
    assert not client.available
    assert not client.supports_wake_word("okay nabu")
    # The entry stays loaded, so it is still there when the app comes back
    assert setup_integration.state is ConfigEntryState.LOADED


async def test_availability_is_reported_on_each_change(
    hass: HomeAssistant, fake_app: FakeApp, setup_integration: MockConfigEntry
) -> None:
    """Test a listener hears the app go and come back, and nothing else.

    The re-read itself is driven here rather than by its timer: freezing
    the clock to reach the timer also expires the request it makes.
    """
    client = setup_integration.runtime_data
    changes: list[bool] = []
    remove = client.async_add_listener(lambda: changes.append(client.available))

    await fake_app.stop()
    with pytest.raises(aiohttp.ClientError):
        await client.async_update_info()
    assert changes == [False]

    # Still gone: the same answer is not reported twice
    with pytest.raises(aiohttp.ClientError):
        await client.async_update_info()
    assert changes == [False]

    await fake_app.start()
    await client.async_update_info()
    assert changes == [False, True]
    assert client.available

    remove()
    await fake_app.stop()
    with pytest.raises(aiohttp.ClientError):
        await client.async_update_info()
    assert changes == [False, True]


async def test_the_preview_feature_gates_the_provider(
    hass: HomeAssistant,
    fake_app: FakeApp,
    config_entry_for: Callable[[FakeApp], MockConfigEntry],
) -> None:
    """Test nothing is asked until the Labs feature is turned on."""
    entry = config_entry_for(fake_app)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert async_get_client(hass) is None

    await async_update_preview_feature(
        hass, DOMAIN, PREVIEW_FEATURE_WAKE_WORD_VERIFICATION, True
    )
    await hass.async_block_till_done()
    assert async_get_client(hass) is entry.runtime_data

    await async_update_preview_feature(
        hass, DOMAIN, PREVIEW_FEATURE_WAKE_WORD_VERIFICATION, False
    )
    await hass.async_block_till_done()
    assert async_get_client(hass) is None
