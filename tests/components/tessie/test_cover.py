"""Test the Tessie cover platform."""

from unittest.mock import patch

import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.cover import (
    DOMAIN as COVER_DOMAIN,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    CoverState,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .common import (
    ERROR_UNKNOWN,
    TEST_RESPONSE,
    TEST_RESPONSE_ERROR,
    assert_entities,
    setup_platform,
)


async def test_covers(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Tests that the window cover entity is correct."""

    entry = await setup_platform(hass, [Platform.COVER])

    assert_entities(hass, entry.entry_id, entity_registry, snapshot)

    for entity_id, openfunc, closefunc in (
        ("cover.test_vent_windows", "vent_windows", "close_windows"),
        ("cover.test_charge_port_door", "open_unlock_charge_port", "close_charge_port"),
        ("cover.test_frunk", "open_front_trunk", False),
        ("cover.test_trunk", "open_close_rear_trunk", "open_close_rear_trunk"),
        ("cover.test_sunroof", "vent_sunroof", "close_sunroof"),
    ):
        # Test open windows
        if openfunc:
            with patch(
                f"homeassistant.components.tessie.cover.{openfunc}",
                return_value=TEST_RESPONSE,
            ) as mock_open:
                await hass.services.async_call(
                    COVER_DOMAIN,
                    SERVICE_OPEN_COVER,
                    {ATTR_ENTITY_ID: [entity_id]},
                    blocking=True,
                )
                mock_open.assert_called_once()
            assert hass.states.get(entity_id).state == CoverState.OPEN

        # Test close windows
        if closefunc:
            with patch(
                f"homeassistant.components.tessie.cover.{closefunc}",
                return_value=TEST_RESPONSE,
            ) as mock_close:
                await hass.services.async_call(
                    COVER_DOMAIN,
                    SERVICE_CLOSE_COVER,
                    {ATTR_ENTITY_ID: [entity_id]},
                    blocking=True,
                )
                mock_close.assert_called_once()
            assert hass.states.get(entity_id).state == CoverState.CLOSED


async def test_errors(hass: HomeAssistant) -> None:
    """Tests errors are handled."""

    await setup_platform(hass, [Platform.COVER])
    entity_id = "cover.test_charge_port_door"

    # Test setting cover open with unknown error
    with (
        patch(
            "homeassistant.components.tessie.cover.open_unlock_charge_port",
            side_effect=ERROR_UNKNOWN,
        ) as mock_set,
        pytest.raises(HomeAssistantError) as error,
    ):
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_OPEN_COVER,
            {ATTR_ENTITY_ID: [entity_id]},
            blocking=True,
        )
    mock_set.assert_called_once()
    assert error.value.__cause__ == ERROR_UNKNOWN

    # Test setting cover open with unknown error
    with (
        patch(
            "homeassistant.components.tessie.cover.open_unlock_charge_port",
            return_value=TEST_RESPONSE_ERROR,
        ) as mock_set,
        pytest.raises(HomeAssistantError) as error,
    ):
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_OPEN_COVER,
            {ATTR_ENTITY_ID: [entity_id]},
            blocking=True,
        )
    mock_set.assert_called_once()
    assert str(error.value) == f"Command failed, {TEST_RESPONSE_ERROR['reason']}"
