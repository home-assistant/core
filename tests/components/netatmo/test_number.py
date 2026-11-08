"""The tests for the Netatmo number platform."""

from unittest.mock import AsyncMock

import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    mock_restore_cache_with_extra_data,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform, UnitOfTemperature
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er

from .common import selected_platforms, snapshot_platform_entities

TEMPERATURE_OFFSET_ENTITY = "number.livingroom_livingroom_temperature_offset"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_entity(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    netatmo_auth: AsyncMock,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test entities."""
    await snapshot_platform_entities(
        hass,
        config_entry,
        Platform.NUMBER,
        entity_registry,
        snapshot,
    )


async def test_temperature_offset_default_and_set_value(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    netatmo_auth: AsyncMock,
) -> None:
    """Test the offset defaults to 0 and can be changed locally."""
    with selected_platforms([Platform.NUMBER]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get(TEMPERATURE_OFFSET_ENTITY).state == "0.0"

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: TEMPERATURE_OFFSET_ENTITY, ATTR_VALUE: 1.5},
        blocking=True,
    )

    assert hass.states.get(TEMPERATURE_OFFSET_ENTITY).state == "1.5"


async def test_temperature_offset_restored(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    netatmo_auth: AsyncMock,
) -> None:
    """Test the offset is restored across restarts since Netatmo does not store it."""
    mock_restore_cache_with_extra_data(
        hass,
        (
            (
                State(TEMPERATURE_OFFSET_ENTITY, "-2.5"),
                {
                    "native_max_value": 5.0,
                    "native_min_value": -5.0,
                    "native_step": 0.1,
                    "native_unit_of_measurement": UnitOfTemperature.CELSIUS,
                    "native_value": -2.5,
                },
            ),
        ),
    )

    with selected_platforms([Platform.NUMBER]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get(TEMPERATURE_OFFSET_ENTITY).state == "-2.5"
