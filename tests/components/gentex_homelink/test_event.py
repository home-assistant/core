"""Test that the devices and entities are correctly configured."""

import time
from unittest.mock import AsyncMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
import homeassistant.helpers.entity_registry as er

from . import setup_integration, update_callback

from tests.common import MockConfigEntry, snapshot_platform
from tests.conftest import AiohttpClientMocker


@pytest.mark.usefixtures("aioclient_mock_fixture")
async def test_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_mqtt_provider: AsyncMock,
    aioclient_mock: AiohttpClientMocker,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Check if the entities are registered."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("aioclient_mock_fixture")
@pytest.mark.freeze_time("2021-07-30")
async def test_entities_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    mock_mqtt_provider: AsyncMock,
) -> None:
    """Check if the entities are updated."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("event.testdevice_button_1").state == STATE_UNKNOWN

    await update_callback(
        hass,
        mock_mqtt_provider,
        "state",
        {
            "1": {"requestId": "rid1", "timestamp": time.time()},
            "2": {"requestId": "rid2", "timestamp": time.time()},
            "3": {"requestId": "rid3", "timestamp": time.time()},
        },
    )
    assert (
        hass.states.get("event.testdevice_button_1").state
        == "2021-07-30T00:00:00.000+00:00"
    )
