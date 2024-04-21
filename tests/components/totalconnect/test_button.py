"""Tests for the TotalConnect buttons."""

from unittest.mock import patch

import pytest
from total_connect_client.exceptions import FailedToBypassZone

from homeassistant.components.button import DOMAIN as BUTTON, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import (
    LOCATION_ID,
    RESPONSE_ZONE_BYPASS_FAILURE,
    RESPONSE_ZONE_BYPASS_SUCCESS,
    TOTALCONNECT_REQUEST,
    ZONE_NORMAL,
    setup_platform,
)

ZONE_BYPASS_ID = "button.security_bypass"
PANEL_CLEAR_ID = "button.test_clear_bypass"
PANEL_BYPASS_ID = "button.test_bypass_all"


async def test_entity_registry(hass: HomeAssistant) -> None:
    """Test the button is registered in entity registry."""
    await setup_platform(hass, BUTTON)
    entity_registry = er.async_get(hass)

    # ensure zone 1 bypass is created
    entry = entity_registry.async_get(ZONE_BYPASS_ID)
    assert entry.unique_id == f"{LOCATION_ID}_{ZONE_NORMAL['ZoneID']}_bypass"

    # ensure panel BypassAll and Clear are created
    panel_bypass = entity_registry.async_get(PANEL_BYPASS_ID)
    panel_clear = entity_registry.async_get(PANEL_CLEAR_ID)

    assert panel_bypass.unique_id == f"{LOCATION_ID}_bypass_all"
    assert panel_clear.unique_id == f"{LOCATION_ID}_clear_bypass"


async def _test_bypass_button(hass: HomeAssistant, data: {}) -> None:
    """Test pushing a bypass button."""
    responses = [RESPONSE_ZONE_BYPASS_FAILURE, RESPONSE_ZONE_BYPASS_SUCCESS]
    await setup_platform(hass, BUTTON)
    with patch(TOTALCONNECT_REQUEST, side_effect=responses) as mock_request:
        # try to bypass, but fails
        with pytest.raises(FailedToBypassZone):
            await hass.services.async_call(
                domain=BUTTON, service=SERVICE_PRESS, service_data=data, blocking=True
            )
            assert mock_request.call_count == 1

        # try to bypass, works this time
        await hass.services.async_call(
            domain=BUTTON, service=SERVICE_PRESS, service_data=data, blocking=True
        )
        assert mock_request.call_count == 2


async def test_zone_bypass(hass: HomeAssistant) -> None:
    """Test pushing the zone bypass button."""
    data = {ATTR_ENTITY_ID: ZONE_BYPASS_ID}
    await _test_bypass_button(hass, data)


async def test_bypass_all(hass: HomeAssistant) -> None:
    """Test pushing the panel bypass all button."""
    data = {ATTR_ENTITY_ID: PANEL_BYPASS_ID}
    await _test_bypass_button(hass, data)


async def test_clear_button(hass: HomeAssistant) -> None:
    """Test pushing the clear bypass button."""
    data = {ATTR_ENTITY_ID: PANEL_CLEAR_ID}
    await setup_platform(hass, BUTTON)
    """ 'clear bypass' is actually just a call to Disarm the panel
    which is tested thoroughly in test_alarm_control_panel.py
    so just make sure it gets called
    """
    TOTALCONNECT_REQUEST = "total_connect_client.location.TotalConnectLocation.disarm"

    with patch(TOTALCONNECT_REQUEST) as mock_request:
        await hass.services.async_call(
            domain=BUTTON, service=SERVICE_PRESS, service_data=data, blocking=True
        )
        assert mock_request.call_count == 1
