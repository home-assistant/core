"""The sensor tests for the Airzone platform."""

from collections.abc import Generator
import copy
from unittest.mock import patch

from aioairzone.const import API_DATA, API_SYSTEMS
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.airzone.coordinator import SCAN_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util.dt import utcnow

from .util import (
    HVAC_DHW_MOCK,
    HVAC_MOCK,
    HVAC_SYSTEMS_MOCK,
    HVAC_VERSION_MOCK,
    HVAC_WEBSERVER_MOCK,
    async_init_integration,
)

from tests.common import async_fire_time_changed, snapshot_platform


@pytest.fixture(autouse=True)
def override_platforms() -> Generator[None]:
    """Override PLATFORMS."""
    with patch("homeassistant.components.airzone.PLATFORMS", [Platform.SENSOR]):
        yield


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_airzone_create_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test creation of sensors."""

    config_entry = await async_init_integration(hass)

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)

    state = hass.states.get("sensor.dkn_plus_humidity")
    assert state is None


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_airzone_sensors_availability(hass: HomeAssistant) -> None:
    """Test sensors availability."""

    await async_init_integration(hass)

    HVAC_MOCK_UNAVAILABLE_ZONE = copy.deepcopy(HVAC_MOCK)
    del HVAC_MOCK_UNAVAILABLE_ZONE[API_SYSTEMS][0][API_DATA][1]

    with (
        patch(
            "homeassistant.components.airzone.AirzoneLocalApi.get_dhw",
            return_value=HVAC_DHW_MOCK,
        ),
        patch(
            "homeassistant.components.airzone.AirzoneLocalApi.get_hvac",
            return_value=HVAC_MOCK_UNAVAILABLE_ZONE,
        ),
        patch(
            "homeassistant.components.airzone.AirzoneLocalApi.get_hvac_systems",
            return_value=HVAC_SYSTEMS_MOCK,
        ),
        patch(
            "homeassistant.components.airzone.AirzoneLocalApi.get_version",
            return_value=HVAC_VERSION_MOCK,
        ),
        patch(
            "homeassistant.components.airzone.AirzoneLocalApi.get_webserver",
            return_value=HVAC_WEBSERVER_MOCK,
        ),
    ):
        async_fire_time_changed(hass, utcnow() + SCAN_INTERVAL)
        await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("sensor.dorm_ppal_temperature")
    assert state.state == STATE_UNAVAILABLE

    state = hass.states.get("sensor.dorm_ppal_humidity")
    assert state.state == STATE_UNAVAILABLE
