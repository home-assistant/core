"""Test pi_hole component."""

import copy
from datetime import timedelta
from unittest.mock import AsyncMock

import pytest

from homeassistant.components import pi_hole
from homeassistant.components.pi_hole.const import CONF_STATISTICS_ONLY
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import CONFIG_DATA_DEFAULTS, ZERO_DATA_V6, _create_mocked_hole, _patch_init_hole

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_bad_data_type(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test handling of bad data. Mostly for code coverage, rather than simulating known error states."""
    mocked_hole = _create_mocked_hole(
        api_version=6, has_data=True, incorrect_app_password=False
    )
    entry = MockConfigEntry(
        domain=pi_hole.DOMAIN, data={**CONFIG_DATA_DEFAULTS, CONF_STATISTICS_ONLY: True}
    )
    entry.add_to_hass(hass)
    with _patch_init_hole(mocked_hole):
        assert await hass.config_entries.async_setup(entry.entry_id)

    bad_data = copy.deepcopy(ZERO_DATA_V6)
    bad_data["queries"]["total"] = "error string"
    assert bad_data != ZERO_DATA_V6

    async def set_bad_data():
        """Set mocked data to bad_data."""
        mocked_hole.instances[-1].data = bad_data

    mocked_hole.instances[-1].get_data = AsyncMock(side_effect=set_bad_data)

    # Wait a minute
    future = dt_util.utcnow() + timedelta(minutes=1)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    assert "TypeError" in caplog.text


async def test_bad_data_key(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test handling of bad data. Mostly for code coverage, rather than simulating known error states."""
    mocked_hole = _create_mocked_hole(
        api_version=6, has_data=True, incorrect_app_password=False
    )
    entry = MockConfigEntry(
        domain=pi_hole.DOMAIN, data={**CONFIG_DATA_DEFAULTS, CONF_STATISTICS_ONLY: True}
    )
    entry.add_to_hass(hass)
    with _patch_init_hole(mocked_hole):
        assert await hass.config_entries.async_setup(entry.entry_id)

    bad_data = copy.deepcopy(ZERO_DATA_V6)
    # remove a whole part of the dict tree now
    bad_data["queries"] = "error string"
    assert bad_data != ZERO_DATA_V6

    async def set_bad_data():
        """Set mocked data to bad_data."""
        mocked_hole.instances[-1].data = bad_data

    mocked_hole.instances[-1].get_data = AsyncMock(side_effect=set_bad_data)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=1))
    await hass.async_block_till_done()
    assert mocked_hole.instances[-1].data != ZERO_DATA_V6

    assert "KeyError" in caplog.text
