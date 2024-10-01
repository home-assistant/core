"""Test subscription websocket api."""

from collections.abc import Generator
import time
from unittest.mock import AsyncMock, patch
import uuid

import pytest

from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from tests.typing import MockHAClientWebSocket


@pytest.fixture
def mock_subscription_flow() -> Generator[AsyncMock]:
    """Mock the ha_event.flow."""
    with patch(
        "homeassistant.components.domika.subscription.router.subscription_flow",
        autospec=True,
    ) as mock_subscription_flow:
        yield mock_subscription_flow


@pytest.mark.usefixtures("database_get_session")
@pytest.mark.usefixtures("init_integration")
@pytest.mark.usefixtures("mock_ha_event_flow")
async def test_resubscribe(
    hass: HomeAssistant,
    websocket_client: MockHAClientWebSocket,
    mock_subscription_flow: AsyncMock,
) -> None:
    """Test resubscribe."""
    timestamp = time.time()

    # Create entity and set state.
    hass.states.async_set(
        entity_id="test_platform.entity_id",
        new_state=STATE_ON,
        attributes={
            "friendly_name": "test_entity",
        },
        timestamp=timestamp,
    )
    await hass.async_block_till_done()

    app_session_id = uuid.uuid4()

    # Websocket request.
    await websocket_client.send_json(
        {
            "id": 5,
            "type": "domika/resubscribe",
            "app_session_id": str(app_session_id),
            "subscriptions": {
                "test_platform.entity_id": [],
            },
        }
    )

    # Websocket result.
    result = await websocket_client.receive_json()
    assert result == {
        "id": 5,
        "type": "result",
        "success": True,
        "result": {
            "entities": [
                {
                    "entity_id": "test_platform.entity_id",
                    "time_updated": dt_util.utc_from_timestamp(timestamp).isoformat(),
                    "attributes": {
                        "a.friendly_name": "test_entity",
                        "s": STATE_ON,
                    },
                }
            ],
        },
    }

    await hass.async_block_till_done()

    mock_subscription_flow.resubscribe.assert_called_once()
