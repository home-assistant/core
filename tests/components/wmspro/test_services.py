"""Test wmspro integration services."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_CURRENT_TILT_POSITION,
    ATTR_POSITION,
    ATTR_TILT_POSITION,
)
from homeassistant.components.wmspro.const import (
    DOMAIN,
    SERVICE_SET_COVER_POSITION_AND_TILT,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OPEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from . import setup_config_entry

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("mock_hub_configuration", "mock_hub_status"),
    [("config_prod_slat_rotate.json", "status_prod_slat_rotate.json")],
    indirect=True,
)
async def test_set_cover_position_and_tilt_service_is_registered(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hub_ping: AsyncMock,
    mock_hub_configuration: AsyncMock,
    mock_hub_status: AsyncMock,
) -> None:
    """Test that set_cover_position_and_tilt service is registered."""
    assert await setup_config_entry(hass, mock_config_entry)
    assert len(mock_hub_ping.mock_calls) == 1
    assert len(mock_hub_configuration.mock_calls) == 1
    assert len(mock_hub_status.mock_calls) == len(mock_hub_configuration.destinations)

    assert hass.services.has_service(DOMAIN, SERVICE_SET_COVER_POSITION_AND_TILT)


@pytest.mark.parametrize(
    ("mock_hub_configuration", "mock_hub_status", "entity_id"),
    [
        (
            "config_prod_slat_rotate.json",
            "status_prod_slat_rotate.json",
            "cover.zonwering_begane_grond_keuken_alle",
        ),
    ],
    indirect=["mock_hub_configuration", "mock_hub_status"],
)
async def test_set_cover_position_and_tilt_service_executes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hub_ping: AsyncMock,
    mock_hub_configuration: AsyncMock,
    mock_hub_status: AsyncMock,
    mock_action_call: AsyncMock,
    mock_action_list_call: AsyncMock,
    entity_id: str,
) -> None:
    """Test set_cover_position_and_tilt updates position and tilt in one action call."""
    assert await setup_config_entry(hass, mock_config_entry)
    assert len(mock_hub_ping.mock_calls) == 1
    assert len(mock_hub_configuration.mock_calls) == 1
    assert len(mock_hub_status.mock_calls) == len(mock_hub_configuration.destinations)

    entity = hass.states.get(entity_id)
    assert entity is not None
    assert entity.attributes[ATTR_CURRENT_POSITION] == 0
    assert entity.attributes[ATTR_CURRENT_TILT_POSITION] == 50

    with patch(
        "wmspro.destination.Destination.refresh",
        return_value=True,
    ):
        before_status = len(mock_hub_status.mock_calls)
        before_action = len(mock_action_call.mock_calls)
        before_action_list = len(mock_action_list_call.mock_calls)

        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_COVER_POSITION_AND_TILT,
            {
                ATTR_ENTITY_ID: entity.entity_id,
                ATTR_POSITION: 30,
                ATTR_TILT_POSITION: 80,
            },
            blocking=True,
        )

        entity = hass.states.get(entity_id)
        assert entity is not None
        assert entity.state == STATE_OPEN
        assert entity.attributes[ATTR_CURRENT_POSITION] == 30
        assert entity.attributes[ATTR_CURRENT_TILT_POSITION] == 80
        assert len(mock_hub_status.mock_calls) == before_status
        assert len(mock_action_call.mock_calls) == before_action + 2
        assert len(mock_action_list_call.mock_calls) == before_action_list + 1


@pytest.mark.parametrize(
    ("mock_hub_configuration", "mock_hub_status", "entity_id"),
    [
        (
            "config_prod_awning_dimmer.json",
            "status_prod_awning.json",
            "cover.terrasse_markise",
        ),
    ],
    indirect=["mock_hub_configuration", "mock_hub_status"],
)
async def test_set_cover_position_and_tilt_unsupported_entity_raises(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hub_ping: AsyncMock,
    mock_hub_configuration: AsyncMock,
    mock_hub_status: AsyncMock,
    entity_id: str,
) -> None:
    """Test set_cover_position_and_tilt raises for entities without tilt support."""
    assert await setup_config_entry(hass, mock_config_entry)
    assert len(mock_hub_ping.mock_calls) == 1
    assert len(mock_hub_configuration.mock_calls) == 1
    assert len(mock_hub_status.mock_calls) == len(mock_hub_configuration.destinations)

    before = len(mock_hub_status.mock_calls)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_COVER_POSITION_AND_TILT,
            {
                ATTR_ENTITY_ID: entity_id,
                ATTR_POSITION: 30,
                ATTR_TILT_POSITION: 80,
            },
            blocking=True,
        )

    assert len(mock_hub_status.mock_calls) == before
