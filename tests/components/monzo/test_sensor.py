"""Tests for the Monzo component."""

from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.monzo.const import DOMAIN
from homeassistant.components.monzo.sensor import (
    ACCOUNT_SENSORS,
    POT_SENSORS,
    MonzoSensorEntityDescription,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import TEST_ACCOUNTS, TEST_POTS

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform
from tests.typing import ClientSessionGenerator

EXPECTED_VALUE_GETTERS = {
    "balance": lambda x: x["balance"]["balance"] / 100,
    "total_balance": lambda x: x["balance"]["total_balance"] / 100,
    "pot_balance": lambda x: x["balance"] / 100,
}


async def async_get_entity_id(
    hass: HomeAssistant,
    acc_id: str,
    description: MonzoSensorEntityDescription,
) -> str | None:
    """Get an entity id for a user's attribute."""
    entity_registry = er.async_get(hass)
    unique_id = f"{acc_id}_{description.key}"

    return entity_registry.async_get_entity_id(SENSOR_DOMAIN, DOMAIN, unique_id)


def async_assert_state_equals(
    entity_id: str,
    state_obj: State,
    expected: Any,
    description: MonzoSensorEntityDescription,
) -> None:
    """Assert at given state matches what is expected."""
    assert state_obj, f"Expected entity {entity_id} to exist but it did not"

    assert state_obj.state == str(expected), (
        f"Expected {expected} but was {state_obj.state} "
        f"for measure {description.name}, {entity_id}"
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_default_enabled_entities(
    hass: HomeAssistant,
    monzo: AsyncMock,
    polling_config_entry: MockConfigEntry,
    hass_client_no_auth: ClientSessionGenerator,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test entities enabled by default."""
    await setup_integration(hass, polling_config_entry)

    for acc in TEST_ACCOUNTS:
        for sensor_description in ACCOUNT_SENSORS:
            entity_id = await async_get_entity_id(hass, acc["id"], sensor_description)
            assert entity_id
            assert entity_registry.async_is_registered(entity_id)

            state = hass.states.get(entity_id)
            assert state.state == str(
                EXPECTED_VALUE_GETTERS[sensor_description.key](acc)
            )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_unavailable_entity(
    hass: HomeAssistant,
    basic_monzo: AsyncMock,
    polling_config_entry: MockConfigEntry,
    hass_client_no_auth: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test entities enabled by default."""
    await setup_integration(hass, polling_config_entry)
    basic_monzo.user_account.pots.return_value = [{"id": "pot_savings"}]
    freezer.tick(timedelta(minutes=100))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    entity_id = await async_get_entity_id(hass, TEST_POTS[0]["id"], POT_SENSORS[0])
    state = hass.states.get(entity_id)
    assert state.state == "unknown"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    monzo: AsyncMock,
    polling_config_entry: MockConfigEntry,
) -> None:
    """Test all entities."""
    await setup_integration(hass, polling_config_entry)

    await snapshot_platform(
        hass, entity_registry, snapshot, polling_config_entry.entry_id
    )


async def test_update_failed(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    monzo: AsyncMock,
    polling_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test all entities."""
    await setup_integration(hass, polling_config_entry)

    monzo.user_account.accounts.side_effect = Exception
    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    entity_id = await async_get_entity_id(
        hass, TEST_ACCOUNTS[0]["id"], ACCOUNT_SENSORS[0]
    )
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
