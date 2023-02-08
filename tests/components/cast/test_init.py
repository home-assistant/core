"""Tests for the Cast integration."""
from unittest.mock import patch

import pytest

from homeassistant.components import cast
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


async def test_import(hass: HomeAssistant, caplog: pytest.LogCaptureFixture) -> None:
    """Test that specifying config will create an entry."""
    with patch(
        "homeassistant.components.cast.async_setup_entry", return_value=True
    ) as mock_setup:
        await async_setup_component(
            hass,
            cast.DOMAIN,
            {
                "cast": {
                    "media_player": [
                        {"uuid": "abcd"},
                        {"uuid": "abcd", "ignore_cec": "milk"},
                        {"uuid": "efgh", "ignore_cec": "beer"},
                        {"incorrect": "config"},
                    ]
                }
            },
        )
        await hass.async_block_till_done()

    assert len(mock_setup.mock_calls) == 1

    assert len(hass.config_entries.async_entries("cast")) == 1
    entry = hass.config_entries.async_entries("cast")[0]
    assert set(entry.data["ignore_cec"]) == {"milk", "beer"}
    assert set(entry.data["uuid"]) == {"abcd", "efgh"}

    assert "Invalid config '{'incorrect': 'config'}'" in caplog.text


async def test_not_configuring_cast_not_creates_entry(hass: HomeAssistant) -> None:
    """Test that an empty config does not create an entry."""
    with patch(
        "homeassistant.components.cast.async_setup_entry", return_value=True
    ) as mock_setup:
        await async_setup_component(hass, cast.DOMAIN, {})
        await hass.async_block_till_done()

    assert len(mock_setup.mock_calls) == 0
