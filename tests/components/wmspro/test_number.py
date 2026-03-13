"""Test the wmspro number support."""

from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.components.wmspro.number import SCAN_INTERVAL
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from . import setup_config_entry, unload_config_entry

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.parametrize(
    "entity_name",
    [
        "number.keuken_alle_rotation",
        "number.keuken_alle_minimum_rotation",
        "number.keuken_alle_maximum_rotation",
    ],
)
async def test_number_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hub_ping: AsyncMock,
    mock_hub_configuration_prod_slat_rotate: AsyncMock,
    mock_hub_status_prod_slat_rotate: AsyncMock,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
    entity_name: str,
) -> None:
    """Test that a number entity is created and updated correctly."""
    assert await setup_config_entry(hass, mock_config_entry)
    assert len(mock_hub_ping.mock_calls) == 1
    assert len(mock_hub_configuration_prod_slat_rotate.mock_calls) == 1
    assert len(mock_hub_status_prod_slat_rotate.mock_calls) == 7

    entity = hass.states.get(entity_name)
    assert entity is not None
    assert entity == snapshot

    # Move time to next update
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert len(mock_hub_status_prod_slat_rotate.mock_calls) >= 10


@pytest.mark.parametrize(
    ("entity_name", "initial_value", "target_value"),
    [
        ("number.keuken_alle_rotation", "127", "80"),
        ("number.keuken_alle_minimum_rotation", "-75", "-50"),
        ("number.keuken_alle_maximum_rotation", "75", "100"),
    ],
)
async def test_number_set_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hub_ping: AsyncMock,
    mock_hub_configuration_prod_slat_rotate: AsyncMock,
    mock_hub_status_prod_slat_rotate: AsyncMock,
    mock_action_call: AsyncMock,
    freezer: FrozenDateTimeFactory,
    entity_name: str,
    initial_value: str,
    target_value: str,
) -> None:
    """Test that a number entity is created and value set correctly."""
    assert await setup_config_entry(hass, mock_config_entry)
    assert len(mock_hub_ping.mock_calls) == 1
    assert len(mock_hub_configuration_prod_slat_rotate.mock_calls) == 1
    assert len(mock_hub_status_prod_slat_rotate.mock_calls) == 7

    entity = hass.states.get(entity_name)
    assert entity is not None
    assert float(entity.state) == float(initial_value)

    with patch(
        "wmspro.destination.Destination.refresh",
        return_value=True,
    ):
        before = len(mock_hub_status_prod_slat_rotate.mock_calls)

        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: entity.entity_id, ATTR_VALUE: float(target_value)},
            blocking=True,
        )

        # Also move time to next update to trigger min/max rotation learning
        freezer.tick(SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

        entity = hass.states.get(entity_name)
        assert entity is not None
        assert float(entity.state) == float(target_value)
        assert len(mock_hub_status_prod_slat_rotate.mock_calls) == before


@pytest.mark.parametrize(
    ("entity_name", "initial_value", "target_value"),
    [
        ("number.keuken_alle_minimum_rotation", "-75", "-50"),
        ("number.keuken_alle_maximum_rotation", "75", "100"),
    ],
)
async def test_number_set_and_restore_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hub_ping: AsyncMock,
    mock_hub_configuration_prod_slat_rotate: AsyncMock,
    mock_hub_status_prod_slat_rotate: AsyncMock,
    mock_action_call: AsyncMock,
    freezer: FrozenDateTimeFactory,
    entity_name: str,
    initial_value: str,
    target_value: str,
) -> None:
    """Test that a number entity is created, value set, and restored correctly."""
    assert await setup_config_entry(hass, mock_config_entry)
    assert len(mock_hub_ping.mock_calls) == 1
    assert len(mock_hub_configuration_prod_slat_rotate.mock_calls) == 1
    assert len(mock_hub_status_prod_slat_rotate.mock_calls) == 7

    entity = hass.states.get(entity_name)
    assert entity is not None
    assert float(entity.state) == float(initial_value)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity.entity_id, ATTR_VALUE: float(target_value)},
        blocking=True,
    )

    entity = hass.states.get(entity_name)
    assert entity is not None
    assert float(entity.state) == float(target_value)

    # Simulate restart by unloading and recreating the entity
    await unload_config_entry(hass, mock_config_entry)
    await setup_config_entry(hass, mock_config_entry)
    entity = hass.states.get(entity_name)
    assert entity is not None
    assert float(entity.state) == float(target_value)
