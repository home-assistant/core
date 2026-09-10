"""Test the wmspro button support."""

from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion
from wmspro.destination import Action

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.components.wmspro.number import SCAN_INTERVAL
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from . import setup_config_entry

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.parametrize(
    ("mock_hub_configuration", "mock_hub_status"),
    [("config_prod_awning_dimmer.json", "status_prod_awning.json")],
    indirect=True,
)
async def test_button_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hub_ping: AsyncMock,
    mock_hub_configuration: AsyncMock,
    mock_hub_status: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that a button entity is created and updated correctly."""
    assert await setup_config_entry(hass, mock_config_entry)
    assert len(mock_hub_ping.mock_calls) == 1
    assert len(mock_hub_configuration.mock_calls) == 1
    assert len(mock_hub_status.mock_calls) == len(mock_hub_configuration.destinations)

    entity = hass.states.get("button.terrasse_markise_identify")
    assert entity is not None
    assert entity == snapshot


@pytest.mark.parametrize(
    ("mock_hub_configuration", "mock_hub_status"),
    [("config_prod_awning_dimmer.json", "status_prod_awning.json")],
    indirect=True,
)
async def test_button_press(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hub_ping: AsyncMock,
    mock_hub_configuration: AsyncMock,
    mock_hub_status: AsyncMock,
    mock_action_call: AsyncMock,
) -> None:
    """Test that a button entity is pressed correctly."""

    assert await setup_config_entry(hass, mock_config_entry)
    assert len(mock_hub_ping.mock_calls) == 1
    assert len(mock_hub_configuration.mock_calls) == 1
    assert len(mock_hub_status.mock_calls) == len(mock_hub_configuration.destinations)

    with patch(
        "wmspro.destination.Destination.refresh",
        return_value=True,
    ):
        before_status = len(mock_hub_status.mock_calls)
        before_action = len(mock_action_call.mock_calls)
        entity = hass.states.get("button.terrasse_markise_identify")
        assert entity is not None
        before_state = entity.state

        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: entity.entity_id},
            blocking=True,
        )

        entity = hass.states.get("button.terrasse_markise_identify")
        assert entity is not None
        assert entity.state != before_state
        assert len(mock_hub_status.mock_calls) == before_status
        assert len(mock_action_call.mock_calls) == before_action + 1


@pytest.mark.parametrize(
    ("button_entity_id", "range_entity_id", "target_value", "original_value"),
    [
        (
            "button.zonwering_begane_grond_keuken_alle_reset_rotation",
            "number.zonwering_begane_grond_keuken_alle_minimum_rotation",
            -50.0,
            -75.0,
        ),
        (
            "button.zonwering_begane_grond_keuken_alle_reset_rotation",
            "number.zonwering_begane_grond_keuken_alle_maximum_rotation",
            100.0,
            75.0,
        ),
    ],
)
@pytest.mark.parametrize(
    ("mock_hub_configuration", "mock_hub_status"),
    [("config_prod_slat_rotate.json", "status_prod_slat_rotate.json")],
    indirect=True,
)
async def test_button_rotation_reset_press(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hub_ping: AsyncMock,
    mock_hub_configuration: AsyncMock,
    mock_hub_status: AsyncMock,
    freezer: FrozenDateTimeFactory,
    button_entity_id: str,
    range_entity_id: str,
    target_value: float,
    original_value: float,
) -> None:
    """Test that the rotation reset button can be pressed."""
    assert await setup_config_entry(hass, mock_config_entry)
    assert len(mock_hub_ping.mock_calls) == 1
    assert len(mock_hub_configuration.mock_calls) == 1
    assert len(mock_hub_status.mock_calls) == len(mock_hub_configuration.destinations)

    entity = hass.states.get(range_entity_id)
    assert entity is not None
    assert float(entity.state) == original_value

    with patch.object(
        Action,
        "__setitem__",
        side_effect=Action.__setitem__,
        autospec=True,
    ) as mock_action_setitem:
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: range_entity_id, ATTR_VALUE: target_value},
            blocking=True,
        )
        assert len(mock_action_setitem.mock_calls) == 1

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    entity = hass.states.get(range_entity_id)
    assert entity is not None
    assert float(entity.state) == target_value

    assert button_entity_id in hass.states.async_entity_ids(BUTTON_DOMAIN)

    with patch.object(
        Action,
        "__delitem__",
        side_effect=Action.__delitem__,
        autospec=True,
    ) as mock_action_delitem:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: button_entity_id},
            blocking=True,
        )
        assert len(mock_action_delitem.mock_calls) == 2

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    entity = hass.states.get(range_entity_id)
    assert entity is not None
    assert float(entity.state) == original_value
