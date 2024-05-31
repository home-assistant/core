"""Tests for Ecovacs services."""

from dataclasses import dataclass
from typing import Any

import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.ecovacs.const import DOMAIN
from homeassistant.components.ecovacs.vacuum import SERVICE_SEND_CUSTOM_COMMAND
from homeassistant.components.vacuum import ATTR_COMMAND, ATTR_PARAMS
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

pytestmark = [pytest.mark.usefixtures("init_integration")]


@dataclass(frozen=True)
class CustomCommandTestCase:
    """Custom command test."""

    entity_id: str
    command: str
    params: dict[str, Any] | list[Any] | None


@pytest.mark.usefixtures("mock_device_execute_response")
@pytest.mark.parametrize(
    ("device_fixture", "tests"),
    [
        (
            "yna5x1",
            [
                CustomCommandTestCase(
                    "vacuum.ozmo_950", "test_custom_command", ["param1", "param2"]
                ),
            ],
        ),
    ],
    ids=["yna5x1"],
)
async def test_send_custom_command_service(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    tests: list[CustomCommandTestCase],
) -> None:
    """Test that number entity snapshots match."""
    for test_case in tests:
        entity_id = test_case.entity_id

        vacuum = hass.states.get(entity_id)
        assert vacuum

        assert snapshot(
            name=f"{entity_id}:custom-command-response"
        ) == await hass.services.async_call(
            DOMAIN,
            SERVICE_SEND_CUSTOM_COMMAND,
            {
                ATTR_ENTITY_ID: entity_id,
                ATTR_COMMAND: test_case.command,
                ATTR_PARAMS: test_case.params,
            },
            blocking=True,
            return_response=True,
        )
