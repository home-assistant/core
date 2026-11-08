"""The tests for the Netatmo number platform."""

from typing import Any
from unittest.mock import AsyncMock, patch

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
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from .common import (
    HOME_ID,
    fake_post_request,
    selected_platforms,
    snapshot_platform_entities,
)

TRUE_TEMPERATURE_ENTITY = "number.livingroom_livingroom_true_temperature"
LIVINGROOM_ROOM_ID = "2746182631"
LIVINGROOM_MEASURED_TEMPERATURE = 19.8


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


async def test_true_temperature_default_and_calibrate(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    netatmo_auth: AsyncMock,
) -> None:
    """Test the entity starts unset and stores the computed offset once calibrated."""
    with selected_platforms([Platform.NUMBER]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(TRUE_TEMPERATURE_ENTITY)
    assert state.state == "unknown"
    assert "offset" not in state.attributes

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: TRUE_TEMPERATURE_ENTITY, ATTR_VALUE: 20.0},
        blocking=True,
    )

    state = hass.states.get(TRUE_TEMPERATURE_ENTITY)
    assert state.state == "20.0"
    assert state.attributes["offset"] == round(
        20.0 - LIVINGROOM_MEASURED_TEMPERATURE, 1
    )


async def test_true_temperature_unknown_measured_temperature(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test calibrating raises when the room's measured temperature is unknown."""

    def clear_measured_temperature(payload: dict[str, Any]) -> None:
        body = payload.get("body")
        if not isinstance(body, dict):
            return
        home = body.get("home")
        if not isinstance(home, dict) or home.get("id") != HOME_ID:
            return
        for room in home.get("rooms", []):
            if room["id"] == LIVINGROOM_ROOM_ID:
                room.pop("therm_measured_temperature", None)

    async def fake_post(*args: Any, **kwargs: Any):
        return await fake_post_request(
            hass, *args, msg_callback=clear_measured_temperature, **kwargs
        )

    with (
        selected_platforms([Platform.NUMBER]),
        patch(
            "homeassistant.components.netatmo.api.AsyncConfigEntryNetatmoAuth"
        ) as mock_auth,
    ):
        mock_auth.return_value.async_post_api_request.side_effect = fake_post
        mock_auth.return_value.async_addwebhook.side_effect = AsyncMock()
        mock_auth.return_value.async_dropwebhook.side_effect = AsyncMock()
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: TRUE_TEMPERATURE_ENTITY, ATTR_VALUE: 20.0},
            blocking=True,
        )


async def test_true_temperature_restored(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    netatmo_auth: AsyncMock,
) -> None:
    """Test the entered temperature and computed offset are restored across restarts."""
    mock_restore_cache_with_extra_data(
        hass,
        (
            (
                State(TRUE_TEMPERATURE_ENTITY, "20.0", attributes={"offset": -1.5}),
                {
                    "native_max_value": 40.0,
                    "native_min_value": 0.0,
                    "native_step": 0.1,
                    "native_unit_of_measurement": UnitOfTemperature.CELSIUS,
                    "native_value": 20.0,
                },
            ),
        ),
    )

    with selected_platforms([Platform.NUMBER]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(TRUE_TEMPERATURE_ENTITY)
    assert state.state == "20.0"
    assert state.attributes["offset"] == -1.5
