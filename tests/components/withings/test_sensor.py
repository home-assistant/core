"""Tests for the Withings component."""
from typing import Any
from unittest.mock import AsyncMock

import pytest
from syrupy import SnapshotAssertion
from withings_api.common import NotifyAppli

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.withings.const import Measurement
from homeassistant.components.withings.entity import WithingsEntityDescription
from homeassistant.components.withings.sensor import SENSORS
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_registry import EntityRegistry

from . import call_webhook, setup_integration
from .common import async_get_entity_id
from .conftest import USER_ID, WEBHOOK_ID

from tests.common import MockConfigEntry
from tests.typing import ClientSessionGenerator

WITHINGS_MEASUREMENTS_MAP: dict[Measurement, WithingsEntityDescription] = {
    attr.measurement: attr for attr in SENSORS
}


EXPECTED_DATA = (
    (Measurement.WEIGHT_KG, 70.0),
    (Measurement.FAT_MASS_KG, 5.0),
    (Measurement.FAT_FREE_MASS_KG, 60.0),
    (Measurement.MUSCLE_MASS_KG, 50.0),
    (Measurement.BONE_MASS_KG, 10.0),
    (Measurement.HEIGHT_M, 2.0),
    (Measurement.FAT_RATIO_PCT, 0.07),
    (Measurement.DIASTOLIC_MMHG, 70.0),
    (Measurement.SYSTOLIC_MMGH, 100.0),
    (Measurement.HEART_PULSE_BPM, 60.0),
    (Measurement.SPO2_PCT, 0.95),
    (Measurement.HYDRATION, 0.95),
    (Measurement.PWV, 100.0),
    (Measurement.SLEEP_BREATHING_DISTURBANCES_INTENSITY, 160.0),
    (Measurement.SLEEP_DEEP_DURATION_SECONDS, 322),
    (Measurement.SLEEP_HEART_RATE_AVERAGE, 164.0),
    (Measurement.SLEEP_HEART_RATE_MAX, 165.0),
    (Measurement.SLEEP_HEART_RATE_MIN, 166.0),
    (Measurement.SLEEP_LIGHT_DURATION_SECONDS, 334),
    (Measurement.SLEEP_REM_DURATION_SECONDS, 336),
    (Measurement.SLEEP_RESPIRATORY_RATE_AVERAGE, 169.0),
    (Measurement.SLEEP_RESPIRATORY_RATE_MAX, 170.0),
    (Measurement.SLEEP_RESPIRATORY_RATE_MIN, 171.0),
    (Measurement.SLEEP_SCORE, 222),
    (Measurement.SLEEP_SNORING, 173.0),
    (Measurement.SLEEP_SNORING_EPISODE_COUNT, 348),
    (Measurement.SLEEP_TOSLEEP_DURATION_SECONDS, 162.0),
    (Measurement.SLEEP_TOWAKEUP_DURATION_SECONDS, 163.0),
    (Measurement.SLEEP_WAKEUP_COUNT, 350),
    (Measurement.SLEEP_WAKEUP_DURATION_SECONDS, 176.0),
)


def async_assert_state_equals(
    entity_id: str,
    state_obj: State,
    expected: Any,
    description: WithingsEntityDescription,
) -> None:
    """Assert at given state matches what is expected."""
    assert state_obj, f"Expected entity {entity_id} to exist but it did not"

    assert state_obj.state == str(expected), (
        f"Expected {expected} but was {state_obj.state} "
        f"for measure {description.measurement}, {entity_id}"
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_default_enabled_entities(
    hass: HomeAssistant,
    withings: AsyncMock,
    config_entry: MockConfigEntry,
    disable_webhook_delay,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Test entities enabled by default."""
    await setup_integration(hass, config_entry)
    entity_registry: EntityRegistry = er.async_get(hass)

    client = await hass_client_no_auth()
    # Assert entities should exist.
    for attribute in SENSORS:
        entity_id = await async_get_entity_id(hass, attribute, USER_ID, SENSOR_DOMAIN)
        assert entity_id
        assert entity_registry.async_is_registered(entity_id)
    resp = await call_webhook(
        hass,
        WEBHOOK_ID,
        {"userid": USER_ID, "appli": NotifyAppli.SLEEP},
        client,
    )
    assert resp.message_code == 0
    resp = await call_webhook(
        hass,
        WEBHOOK_ID,
        {"userid": USER_ID, "appli": NotifyAppli.WEIGHT},
        client,
    )
    assert resp.message_code == 0

    for measurement, expected in EXPECTED_DATA:
        attribute = WITHINGS_MEASUREMENTS_MAP[measurement]
        entity_id = await async_get_entity_id(hass, attribute, USER_ID, SENSOR_DOMAIN)
        state_obj = hass.states.get(entity_id)

        async_assert_state_equals(entity_id, state_obj, expected, attribute)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    withings: AsyncMock,
    disable_webhook_delay,
    config_entry: MockConfigEntry,
) -> None:
    """Test all entities."""
    await setup_integration(hass, config_entry)

    for sensor in SENSORS:
        entity_id = await async_get_entity_id(hass, sensor, USER_ID, SENSOR_DOMAIN)
        assert hass.states.get(entity_id) == snapshot
