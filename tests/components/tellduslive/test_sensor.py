"""Tests for the Telldus Live diagnostic sensors."""

from datetime import timedelta
from unittest.mock import MagicMock

import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.tellduslive.api import TelldusLiveRateLimitError
from homeassistant.components.tellduslive.const import DOMAIN
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util

STATUS = "sensor.telldus_live_status"
REQUESTS = "sensor.telldus_live_requests_per_hour"


@pytest.mark.usefixtures("mock_tellduslive")
async def test_diagnostic_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the diagnostic sensors and their service device."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await mock_config_entry.runtime_data.setup_task
    await hass.async_block_till_done()

    assert hass.states.get(STATUS).state == "ok"
    assert hass.states.get(REQUESTS).state == "0"
    assert hass.states.get(REQUESTS).attributes["unit_of_measurement"] == "requests/h"
    for entity_id, key in ((STATUS, "status"), (REQUESTS, "requests_per_hour")):
        entry = entity_registry.async_get(entity_id)
        assert entry.entity_category is EntityCategory.DIAGNOSTIC
        assert entry.unique_id == f"{mock_config_entry.entry_id}-{key}"
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_config_entry.entry_id), mock_config_entry.entry_id
    )
    assert device.name == "Telldus Live"


async def test_sensors_follow_refresh(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tellduslive: MagicMock,
) -> None:
    """Test the sensors update after each refresh, including failed ones."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await mock_config_entry.runtime_data.setup_task
    await hass.async_block_till_done()

    mock_tellduslive.ok_responses_last_hour.return_value = 7
    mock_tellduslive.update.side_effect = TelldusLiveRateLimitError("limited", 10)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=61))
    await hass.async_block_till_done()

    assert hass.states.get(REQUESTS).state == "7"
    assert hass.states.get(STATUS).state == "retrying"
