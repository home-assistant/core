"""Tests for the Stookwijzer sensor platform."""

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.stookwijzer.const import DOMAIN
from homeassistant.core import HomeAssistant


@pytest.mark.usefixtures("init_integration")
async def test_service_get_forecast(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Stookwijzer entities."""

    response = await hass.services.async_call(
        DOMAIN,
        "get_forecast",
        {
            "entity_id": "sensor.stookwijzer_advice_code",
        },
        blocking=True,
        return_response=True,
    )

    assert response == snapshot
