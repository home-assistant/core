"""Tests for Fritz!Tools."""

from unittest.mock import patch

import pytest

from homeassistant.components.device_tracker import (
    CONF_CONSIDER_HOME,
    DEFAULT_CONSIDER_HOME,
)
from homeassistant.components.fritz.const import (
    DOMAIN,
    FRITZ_AUTH_EXCEPTIONS,
    FRITZ_EXCEPTIONS,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .const import MOCK_USER_DATA

from tests.common import MockConfigEntry


async def test_setup(hass: HomeAssistant, fc_class_mock, fh_class_mock) -> None:
    """Test setup and unload of Fritz!Tools."""

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_options_reload(
    hass: HomeAssistant, fc_class_mock, fh_class_mock
) -> None:
    """Test reload of Fritz!Tools, when options changed."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_USER_DATA,
        options={CONF_CONSIDER_HOME: DEFAULT_CONSIDER_HOME.total_seconds()},
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_reload",
        return_value=None,
    ) as mock_reload:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.LOADED

        result = await hass.config_entries.options.async_init(entry.entry_id)
        await hass.async_block_till_done()
        await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={CONF_CONSIDER_HOME: 60},
        )
        await hass.async_block_till_done()
        mock_reload.assert_called_once()


@pytest.mark.parametrize(
    "error",
    FRITZ_AUTH_EXCEPTIONS,
)
async def test_setup_auth_fail(hass: HomeAssistant, error) -> None:
    """Test starting a flow by user with an already configured device."""

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.fritz.coordinator.FritzConnection",
        side_effect=error,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR


@pytest.mark.parametrize(
    "error",
    FRITZ_EXCEPTIONS,
)
async def test_setup_fail(hass: HomeAssistant, error) -> None:
    """Test starting a flow by user with an already configured device."""

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.fritz.coordinator.FritzConnection",
        side_effect=error,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
