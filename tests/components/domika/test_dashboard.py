"""Test dashboard websocket api."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch
import uuid

from domika_ha_framework.dashboard.models import Dashboard
from domika_ha_framework.device.models import Device
import pytest

from homeassistant.core import HomeAssistant

from tests.common import async_capture_events
from tests.typing import MockHAClientWebSocket


@pytest.fixture
def mock_device_service() -> Generator[AsyncMock, None, None]:
    """Mock the dashboard.router.device_service."""
    with patch(
        "homeassistant.components.domika.dashboard.router.device_service",
        autospec=True,
    ) as mock_device_service:
        yield mock_device_service


@pytest.fixture
def mock_dashboard_service() -> Generator[AsyncMock, None, None]:
    """Mock the dashboard.router.dashboard_service."""
    with patch(
        "homeassistant.components.domika.dashboard.router.dashboard_service",
        autospec=True,
    ) as mock_dashboard_service:
        yield mock_dashboard_service


@pytest.mark.usefixtures("database_get_session")
@pytest.mark.usefixtures("init_integration")
async def test_update_dashboards(
    hass: HomeAssistant,
    websocket_client: MockHAClientWebSocket,
    mock_dashboard_service: AsyncMock,
    mock_device_service: AsyncMock,
) -> None:
    """Test domika/update_dashboards."""
    app_session_id = uuid.uuid4()
    hash_ = "hash"
    mock_device_service.get_by_user_id.return_value = [
        Device(
            app_session_id=app_session_id,
            user_id="user_id",
            push_session_id=None,
            push_token_hash=hash_,
            last_update=0,
        ),
    ]

    # Capture events.
    events = async_capture_events(hass, f"domika_{app_session_id}")

    # Websocket request.
    await websocket_client.send_json(
        {
            "id": 5,
            "type": "domika/update_dashboards",
            "dashboards": "",
            "hash": hash_,
        }
    )

    # Websocket result.
    result = await websocket_client.receive_json()
    assert result == {
        "id": 5,
        "type": "result",
        "success": True,
        "result": {"result": "accepted"},
    }

    await hass.async_block_till_done()

    mock_dashboard_service.create_or_update.assert_called_once()

    # Sent events.
    assert len(events) == 1
    events[0].data = {
        "d.type": "dashboard_update",
        "hash": hash_,
    }


@pytest.mark.parametrize(
    ("returned_dashboard", "expected_result"),
    [
        (
            Dashboard(
                user_id="user_id",
                dashboards="dashboards",
                hash="hash",
            ),
            {
                "dashboards": "dashboards",
                "hash": "hash",
            },
        ),
        (
            None,
            {
                "dashboards": "",
                "hash": "",
            },
        ),
    ],
)
@pytest.mark.usefixtures("database_get_session")
@pytest.mark.usefixtures("init_integration")
async def test_get_dashboards(
    websocket_client: MockHAClientWebSocket,
    mock_dashboard_service: AsyncMock,
    returned_dashboard: Dashboard | None,
    expected_result: dict[str, str],
) -> None:
    """Test domika/get_dashboards."""
    mock_dashboard_service.get.return_value = returned_dashboard

    # Websocket request.
    await websocket_client.send_json(
        {
            "id": 5,
            "type": "domika/get_dashboards",
        }
    )

    # Websocket result.
    result = await websocket_client.receive_json()
    assert result == {
        "id": 5,
        "type": "result",
        "success": True,
        "result": expected_result,
    }


@pytest.mark.parametrize(
    ("returned_dashboard", "expected_result"),
    [
        (
            Dashboard(
                user_id="user_id",
                dashboards="dashboards",
                hash="hash",
            ),
            {
                "hash": "hash",
            },
        ),
        (
            None,
            {
                "hash": "",
            },
        ),
    ],
)
@pytest.mark.usefixtures("database_get_session")
@pytest.mark.usefixtures("init_integration")
async def test_get_dashboards_hash(
    websocket_client: MockHAClientWebSocket,
    mock_dashboard_service: AsyncMock,
    returned_dashboard: Dashboard | None,
    expected_result: dict[str, str],
) -> None:
    """Test domika/get_dashboards_hash."""
    mock_dashboard_service.get.return_value = returned_dashboard

    # Websocket request.
    await websocket_client.send_json(
        {
            "id": 5,
            "type": "domika/get_dashboards_hash",
        }
    )

    # Websocket result.
    result = await websocket_client.receive_json()
    assert result == {
        "id": 5,
        "type": "result",
        "success": True,
        "result": expected_result,
    }
