"""Test the Tessie lock platform."""

from unittest.mock import patch

from homeassistant.components.lock import (
    DOMAIN as LOCK_DOMAIN,
    SERVICE_LOCK,
    SERVICE_UNLOCK,
)
from homeassistant.components.tessie.const import TessieCategory
from homeassistant.const import ATTR_ENTITY_ID, STATE_LOCKED, STATE_UNLOCKED
from homeassistant.core import HomeAssistant

from .common import TEST_RESPONSE, TEST_VEHICLE_STATE_ONLINE, setup_platform


async def test_locks(hass: HomeAssistant) -> None:
    """Tests that the sensors are correct."""

    assert len(hass.states.async_all("lock")) == 0

    await setup_platform(hass)

    assert len(hass.states.async_all("lock")) == 1

    assert (
        hass.states.get("lock.test_lock").state == STATE_LOCKED
    ) == TEST_VEHICLE_STATE_ONLINE[TessieCategory.VEHICLE_STATE]["locked"]

    # Test lock set value functions
    with patch(
        "homeassistant.components.tessie.lock.lock",
        return_value=TEST_RESPONSE,
    ) as mock_run:
        await hass.services.async_call(
            LOCK_DOMAIN,
            SERVICE_LOCK,
            {ATTR_ENTITY_ID: ["lock.test_lock"]},
            blocking=True,
        )
        assert hass.states.get("lock.test_lock").state == STATE_LOCKED
        mock_run.assert_called_once()

    with patch(
        "homeassistant.components.tessie.lock.unlock",
        return_value=TEST_RESPONSE,
    ) as mock_run:
        await hass.services.async_call(
            LOCK_DOMAIN,
            SERVICE_UNLOCK,
            {ATTR_ENTITY_ID: ["lock.test_lock"]},
            blocking=True,
        )
        assert hass.states.get("lock.test_lock").state == STATE_UNLOCKED
        mock_run.assert_called_once()
