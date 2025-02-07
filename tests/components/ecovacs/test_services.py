"""Tests for Ecovacs services."""

from collections.abc import Generator
from typing import Any
from unittest.mock import patch

from deebot_client.device import Device
import pytest

from homeassistant.components.ecovacs.const import DOMAIN
from homeassistant.components.ecovacs.vacuum import SERVICE_RAW_GET_POSITIONS
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

pytestmark = [pytest.mark.usefixtures("init_integration")]


@pytest.fixture
def mock_device_execute_response(data: dict[str, Any]) -> Generator[dict[str, Any]]:
    """Mock the device execute function response."""

    response = {
        "ret": "ok",
        "resp": {
            "header": {
                "pri": 1,
                "tzm": 480,
                "ts": "1717113600000",
                "ver": "0.0.1",
                "fwVer": "1.2.0",
                "hwVer": "0.1.0",
            },
            "body": {
                "code": 0,
                "msg": "ok",
                "data": data,
            },
        },
        "id": "xRV3",
        "payloadType": "j",
    }

    with patch.object(
        Device,
        "execute_command",
        return_value=response,
    ):
        yield response


@pytest.mark.usefixtures("mock_device_execute_response")
@pytest.mark.parametrize(
    "data",
    [
        {
            "deebotPos": {"x": 1, "y": 5, "a": 85},
            "chargePos": {"x": 5, "y": 9, "a": 85},
        },
        {
            "deebotPos": {"x": 375, "y": 313, "a": 90},
            "chargePos": [{"x": 112, "y": 768, "a": 32}, {"x": 489, "y": 322, "a": 0}],
        },
    ],
)
@pytest.mark.parametrize(
    ("device_fixture", "entity_id"),
    [
        ("yna5x1", "vacuum.ozmo_950"),
    ],
    ids=["yna5x1"],
)
async def test_get_positions_service(
    hass: HomeAssistant,
    mock_device_execute_response: dict[str, Any],
    entity_id: str,
) -> None:
    """Test that get_positions service response snapshots match."""
    vacuum = hass.states.get(entity_id)
    assert vacuum

    assert await hass.services.async_call(
        DOMAIN,
        SERVICE_RAW_GET_POSITIONS,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
        return_response=True,
    ) == {entity_id: mock_device_execute_response}
