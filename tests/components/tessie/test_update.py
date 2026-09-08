"""Test the Tessie update platform."""

from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion
from tesla_fleet_api.exceptions import UnsupportedVehicle

from homeassistant.components.update import (
    ATTR_IN_PROGRESS,
    DOMAIN as UPDATE_DOMAIN,
    SERVICE_INSTALL,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .common import ERROR_UNKNOWN, assert_entities, setup_platform


async def test_updates(
    hass: HomeAssistant, snapshot: SnapshotAssertion, entity_registry: er.EntityRegistry
) -> None:
    """Tests that update entity is correct."""

    entry = await setup_platform(hass, [Platform.UPDATE])

    assert_entities(hass, entry.entry_id, entity_registry, snapshot)

    entity_id = "update.test_update"

    with patch(
        "tesla_fleet_api.tessie.Vehicle.tessie_schedule_software_update"
    ) as mock_update:
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: [entity_id]},
            blocking=True,
        )
        mock_update.assert_called_once()

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_IN_PROGRESS) == 1


async def test_update_error(hass: HomeAssistant) -> None:
    """Test update transport errors are translated."""

    await setup_platform(hass, [Platform.UPDATE])

    with (
        patch(
            "tesla_fleet_api.tessie.Vehicle.tessie_schedule_software_update",
            side_effect=ERROR_UNKNOWN,
        ) as mock_update,
        pytest.raises(HomeAssistantError) as error,
    ):
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: ["update.test_update"]},
            blocking=True,
        )

    mock_update.assert_called_once()
    assert error.value.__cause__ == ERROR_UNKNOWN
    assert error.value.translation_domain == "tessie"
    assert error.value.translation_key == "cannot_connect"

    with (
        patch(
            "tesla_fleet_api.tessie.Vehicle.tessie_schedule_software_update",
            side_effect=UnsupportedVehicle(),
        ) as mock_update,
        pytest.raises(HomeAssistantError) as error,
    ):
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: ["update.test_update"]},
            blocking=True,
        )

    mock_update.assert_called_once()
    assert isinstance(error.value.__cause__, UnsupportedVehicle)
    assert error.value.translation_domain == "tessie"
    assert error.value.translation_key == "command_failed"
