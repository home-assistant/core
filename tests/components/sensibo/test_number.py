"""The test for the sensibo number platform."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import async_fire_time_changed, snapshot_platform


@pytest.mark.parametrize(
    "load_platforms",
    [[Platform.NUMBER]],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_number(
    hass: HomeAssistant,
    load_int: ConfigEntry,
    mock_client: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the Sensibo number."""

    await snapshot_platform(hass, entity_registry, snapshot, load_int.entry_id)

    mock_client.async_get_devices_data.return_value.parsed[
        "ABC999111"
    ].calibration_temp = 0.2

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("number.hallway_temperature_calibration")
    assert state.state == "0.2"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_number_set_value(
    hass: HomeAssistant, load_int: ConfigEntry, mock_client: MagicMock
) -> None:
    """Test the Sensibo number service."""

    state = hass.states.get("number.hallway_temperature_calibration")
    assert state.state == "0.1"

    mock_client.async_set_calibration.return_value = {"status": "failure"}

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: state.entity_id, ATTR_VALUE: "0.2"},
            blocking=True,
        )

    state = hass.states.get("number.hallway_temperature_calibration")
    assert state.state == "0.1"

    mock_client.async_set_calibration.return_value = {"status": "success"}

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: state.entity_id, ATTR_VALUE: "0.2"},
        blocking=True,
    )

    state = hass.states.get("number.hallway_temperature_calibration")
    assert state.state == "0.2"
