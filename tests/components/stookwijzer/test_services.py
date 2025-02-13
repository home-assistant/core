"""Tests for the Stookwijzer sensor platform."""

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.stookwijzer.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("init_integration")
async def test_service_get_forecast(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the Stookwijzer entities."""

    assert snapshot == await hass.services.async_call(
        DOMAIN,
        "get_forecast",
        {
            "device_id": entity_registry.async_device_ids()[0],
        },
        blocking=True,
        return_response=True,
    )
