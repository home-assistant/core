"""Tests for Islamic Prayer Times init."""

from unittest.mock import patch

import pytest
import prayer_times_calculator

from tests.common import MockConfigEntry, mock_coro

from homeassistant.components import islamic_prayer_times
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.setup import async_setup_component


MOCK_ENTRY = MockConfigEntry(domain=islamic_prayer_times.DOMAIN, data={},)


async def test_setup_with_no_config(hass):
    """Test that we do not discover anything or try to set up a Islamic Prayer Times."""
    assert await async_setup_component(hass, islamic_prayer_times.DOMAIN, {}) is True
    assert islamic_prayer_times.DOMAIN not in hass.data


async def test_setup_with_config(hass):
    """Test that we import the config and setup the client."""
    config = {
        islamic_prayer_times.DOMAIN: {islamic_prayer_times.CONF_CALC_METHOD: "isna"}
    }
    assert (
        await async_setup_component(hass, islamic_prayer_times.DOMAIN, config) is True
    )


async def test_successful_config_entry(hass):
    """Test that Islamic Prayer Times is configured successfully."""

    entry = MOCK_ENTRY
    entry.add_to_hass(hass)

    assert await islamic_prayer_times.async_setup_entry(hass, entry) is True
    assert entry.options == {
        islamic_prayer_times.CONF_CALC_METHOD: islamic_prayer_times.DEFAULT_CALC_METHOD
    }


async def test_setup_failed(hass):
    """Test Islamic Prayer Times failed due to an error."""

    entry = MOCK_ENTRY
    entry.add_to_hass(hass)

    # test request error raising ConfigEntryNotReady
    with patch(
        "prayer_times_calculator.PrayerTimesCalculator.fetch_prayer_times",
        side_effect=prayer_times_calculator.exceptions.InvalidResponseError(),
    ), pytest.raises(ConfigEntryNotReady):

        await islamic_prayer_times.async_setup_entry(hass, entry)


async def test_unload_entry(hass):
    """Test removing Islamic Prayer Times."""
    entry = MOCK_ENTRY
    entry.add_to_hass(hass)

    with patch.object(
        hass.config_entries, "async_forward_entry_unload", return_value=mock_coro(True)
    ) as unload_entry:
        assert await islamic_prayer_times.async_setup_entry(hass, entry)

        assert await islamic_prayer_times.async_unload_entry(hass, entry)
        assert unload_entry.call_count == 1
        assert islamic_prayer_times.DOMAIN not in hass.data
