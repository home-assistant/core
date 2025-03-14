"""Tests for the TotalConnect buttons."""

from unittest.mock import patch

import pytest
from syrupy import SnapshotAssertion
from total_connect_client.exceptions import FailedToBypassZone

from homeassistant.components.button import DOMAIN as BUTTON, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import setup_platform

from tests.common import snapshot_platform

ZONE_BYPASS_ID = "button.security_bypass"
PANEL_CLEAR_ID = "button.test_clear_bypass"
PANEL_BYPASS_ID = "button.test_bypass_all"


async def test_entity_registry(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, snapshot: SnapshotAssertion
) -> None:
    """Test the button is registered in entity registry."""
    entry = await setup_platform(hass, BUTTON)

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


@pytest.mark.parametrize(
    ("entity_id", "tcc_request"),
    [
        (ZONE_BYPASS_ID, "total_connect_client.zone.TotalConnectZone.bypass"),
        (
            PANEL_BYPASS_ID,
            "total_connect_client.location.TotalConnectLocation.zone_bypass_all",
        ),
    ],
)
async def test_bypass_button(
    hass: HomeAssistant, entity_id: str, tcc_request: str
) -> None:
    """Test pushing a bypass button."""
    responses = [FailedToBypassZone, None]
    await setup_platform(hass, BUTTON)
    with patch(tcc_request, side_effect=responses) as mock_request:
        # try to bypass, but fails
        with pytest.raises(FailedToBypassZone):
            await hass.services.async_call(
                domain=BUTTON,
                service=SERVICE_PRESS,
                service_data={ATTR_ENTITY_ID: entity_id},
                blocking=True,
            )
        assert mock_request.call_count == 1

        # try to bypass, works this time
        await hass.services.async_call(
            domain=BUTTON,
            service=SERVICE_PRESS,
            service_data={ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        assert mock_request.call_count == 2


async def test_clear_button(hass: HomeAssistant) -> None:
    """Test pushing the clear bypass button."""
    data = {ATTR_ENTITY_ID: PANEL_CLEAR_ID}
    await setup_platform(hass, BUTTON)
    TOTALCONNECT_REQUEST = (
        "total_connect_client.location.TotalConnectLocation.clear_bypass"
    )

    with patch(TOTALCONNECT_REQUEST) as mock_request:
        await hass.services.async_call(
            domain=BUTTON,
            service=SERVICE_PRESS,
            service_data=data,
            blocking=True,
        )
        assert mock_request.call_count == 1
