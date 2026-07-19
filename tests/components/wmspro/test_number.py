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
    "entity_id",
    [
        "number.zonwering_begane_grond_keuken_alle_raw_rotation",
        "number.zonwering_begane_grond_keuken_alle_minimum_rotation",
        "number.zonwering_begane_grond_keuken_alle_maximum_rotation",
    ],
)
@pytest.mark.parametrize(
    ("mock_hub_configuration", "mock_hub_status"),
    [("config_prod_slat_rotate.json", "status_prod_slat_rotate.json")],
    indirect=True,
)
async def test_number_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hub_ping: AsyncMock,
    mock_hub_configuration: AsyncMock,
    mock_hub_status: AsyncMock,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
    entity_id: str,
) -> None:
    """Test that a number entity is created and updated correctly."""
    assert await setup_config_entry(hass, mock_config_entry)
    assert len(mock_hub_ping.mock_calls) == 1
    assert len(mock_hub_configuration.mock_calls) == 1
    assert len(mock_hub_status.mock_calls) == len(mock_hub_configuration.destinations)

    entity = hass.states.get(entity_id)
    assert entity is not None
    assert entity == snapshot

    before_status = len(mock_hub_status.mock_calls)

    # Move time to next update
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert len(mock_hub_status.mock_calls) == before_status + 28


@pytest.mark.parametrize(
    ("entity_id", "initial_value", "target_value", "num_action"),
    [
        ("number.zonwering_begane_grond_keuken_alle_raw_rotation", "0", "80", 1),
        ("number.zonwering_begane_grond_keuken_alle_minimum_rotation", "-75", "-50", 0),
        ("number.zonwering_begane_grond_keuken_alle_maximum_rotation", "75", "100", 0),
    ],
)
@pytest.mark.parametrize(
    ("mock_hub_configuration", "mock_hub_status"),
    [("config_prod_slat_rotate.json", "status_prod_slat_rotate.json")],
    indirect=True,
)
async def test_number_set_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hub_ping: AsyncMock,
    mock_hub_configuration: AsyncMock,
    mock_hub_status: AsyncMock,
    mock_action_call: AsyncMock,
    freezer: FrozenDateTimeFactory,
    entity_id: str,
    initial_value: str,
    target_value: str,
    num_action: int,
) -> None:
    """Test that a number entity is created and value set correctly."""
    assert await setup_config_entry(hass, mock_config_entry)
    assert len(mock_hub_ping.mock_calls) == 1
    assert len(mock_hub_configuration.mock_calls) == 1
    assert len(mock_hub_status.mock_calls) == len(mock_hub_configuration.destinations)

    entity = hass.states.get(entity_id)
    assert entity is not None
    assert float(entity.state) == float(initial_value)

    with patch(
        "wmspro.destination.Destination.refresh",
        return_value=True,
    ):
        before_status = len(mock_hub_status.mock_calls)
        before_action = len(mock_action_call.mock_calls)

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

        entity = hass.states.get(entity_id)
        assert entity is not None
        assert float(entity.state) == float(target_value)
        assert len(mock_hub_status.mock_calls) == before_status
        assert len(mock_action_call.mock_calls) == before_action + num_action


@pytest.mark.parametrize(
    ("entity_id", "initial_value", "target_value"),
    [
        ("number.zonwering_begane_grond_keuken_alle_minimum_rotation", "-75", "-50"),
        ("number.zonwering_begane_grond_keuken_alle_maximum_rotation", "75", "100"),
    ],
)
@pytest.mark.parametrize(
    ("mock_hub_configuration", "mock_hub_status"),
    [("config_prod_slat_rotate.json", "status_prod_slat_rotate.json")],
    indirect=True,
)
async def test_number_set_and_restore_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hub_ping: AsyncMock,
    mock_hub_configuration: AsyncMock,
    mock_hub_status: AsyncMock,
    entity_id: str,
    initial_value: str,
    target_value: str,
) -> None:
    """Test that a number entity is created, value set, and restored correctly."""
    assert await setup_config_entry(hass, mock_config_entry)
    assert len(mock_hub_ping.mock_calls) == 1
    assert len(mock_hub_configuration.mock_calls) == 1
    assert len(mock_hub_status.mock_calls) == len(mock_hub_configuration.destinations)

    entity = hass.states.get(entity_id)
    assert entity is not None
    assert float(entity.state) == float(initial_value)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity.entity_id, ATTR_VALUE: float(target_value)},
        blocking=True,
    )

    entity = hass.states.get(entity_id)
    assert entity is not None
    assert float(entity.state) == float(target_value)

    # Simulate restart by unloading and recreating the entity
    assert await unload_config_entry(hass, mock_config_entry)
    assert await setup_config_entry(hass, mock_config_entry)
    entity = hass.states.get(entity_id)
    assert entity is not None
    assert float(entity.state) == float(target_value)


@pytest.mark.parametrize(
    ("mock_hub_configuration", "mock_hub_status"),
    [("config_prod_slat_rotate.json", "status_prod_slat_rotate.json")],
    indirect=True,
)
async def test_number_update_handles_zero_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hub_ping: AsyncMock,
    mock_hub_configuration: AsyncMock,
    mock_hub_status: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test update path when native value is zero."""
    assert await setup_config_entry(hass, mock_config_entry)
    assert len(mock_hub_ping.mock_calls) == 1
    assert len(mock_hub_configuration.mock_calls) == 1
    assert len(mock_hub_status.mock_calls) == len(mock_hub_configuration.destinations)

    entity = hass.states.get(
        "number.zonwering_begane_grond_keuken_alle_minimum_rotation"
    )
    assert entity is not None

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity.entity_id, ATTR_VALUE: 0.0},
        blocking=True,
    )

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    entity = hass.states.get(
        "number.zonwering_begane_grond_keuken_alle_minimum_rotation"
    )
    assert entity is not None
    assert float(entity.state) == 0.0
