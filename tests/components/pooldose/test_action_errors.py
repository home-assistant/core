"""Test the PoolDose write-action error handling."""

from __future__ import annotations

import enum
from unittest.mock import AsyncMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from tests.common import MockConfigEntry


def _normalize_state(state):
    """Return a mutable, redacted dict for snapshot comparison."""
    if not state:
        return state

    def _convert(value):
        # Enum -> value
        if isinstance(value, enum.Enum):
            return value.value
        # dict-like
        if isinstance(value, dict):
            return {k: _convert(v) for k, v in value.items()}
        # list/tuple
        if isinstance(value, (list, tuple)):
            return [_convert(v) for v in value]
        return value

    data = _convert(dict(state.as_dict()))
    # remove dynamic timestamps
    data.pop("last_changed", None)
    data.pop("last_updated", None)
    data.pop("last_reported", None)
    # redact context id
    if "context" in data:
        data["context"] = {"id": "<context>", "parent_id": None, "user_id": None}
    return data


@pytest.fixture
def platforms() -> list[Platform]:
    """Load number, switch and select platforms for these tests."""
    return [Platform.NUMBER, Platform.SWITCH, Platform.SELECT]


@pytest.mark.parametrize(
    ("service", "domain", "payload"),
    [
        (
            "number.set_value",
            "number",
            {"entity_id": "number.pool_device_ph_target", "value": 7.0},
        ),
        (
            "switch.turn_on",
            "switch",
            {"entity_id": "switch.pool_device_pause_dosing"},
        ),
        (
            "select.select_option",
            "select",
            {"entity_id": "select.pool_device_ph_dosing_set", "option": "acid"},
        ),
    ],
)
async def test_actions_cannot_connect(
    hass: HomeAssistant,
    mock_pooldose_client: AsyncMock,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
    service: str,
    domain: str,
    payload: dict,
) -> None:
    """When the client write method raises, ServiceValidationError('cannot_connect') is raised.

    Use `snapshot` to record the entity state before and after the failed write.
    """
    # runtime client provided by the test fixture
    client = mock_pooldose_client

    # snapshot entity state before attempted write
    entity_id = payload["entity_id"]
    before = hass.states.get(entity_id)
    snapshot.assert_match(_normalize_state(before))

    # Configure the appropriate method to raise a ServiceValidationError
    err = ServiceValidationError(
        translation_domain="pooldose",
        translation_key="cannot_connect",
        translation_placeholders={"error": "mocked error"},
    )

    if domain == "number":
        client.set_number = AsyncMock(side_effect=err)
    elif domain == "switch":
        client.set_switch = AsyncMock(side_effect=err)
    else:
        client.set_select = AsyncMock(side_effect=err)

    with pytest.raises(ServiceValidationError) as excinfo:
        await hass.services.async_call(
            service.split(".")[0], service.split(".")[1], payload, blocking=True
        )

    assert excinfo.value.translation_key == "cannot_connect"

    # after: entity state should be unchanged
    after = hass.states.get(entity_id)
    snapshot.assert_match(_normalize_state(after))


@pytest.mark.parametrize(
    ("service", "domain", "payload"),
    [
        (
            "number.set_value",
            "number",
            {"entity_id": "number.pool_device_ph_target", "value": 7.0},
        ),
        (
            "switch.turn_on",
            "switch",
            {"entity_id": "switch.pool_device_pause_dosing"},
        ),
        (
            "select.select_option",
            "select",
            {"entity_id": "select.pool_device_ph_dosing_set", "option": "acid"},
        ),
    ],
)
async def test_actions_write_rejected(
    hass: HomeAssistant,
    mock_pooldose_client: AsyncMock,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
    service: str,
    domain: str,
    payload: dict,
) -> None:
    """When the client write method returns False, ServiceValidationError('write_rejected') is raised.

    Use `snapshot` to record the entity state before and after the failed write.
    """
    client = mock_pooldose_client

    entity_id = payload["entity_id"]
    before = hass.states.get(entity_id)
    snapshot.assert_match(_normalize_state(before))

    if domain == "number":
        client.set_number = AsyncMock(return_value=False)
    elif domain == "switch":
        client.set_switch = AsyncMock(return_value=False)
    else:
        client.set_select = AsyncMock(return_value=False)

    with pytest.raises(ServiceValidationError) as excinfo:
        await hass.services.async_call(
            service.split(".")[0], service.split(".")[1], payload, blocking=True
        )

    assert excinfo.value.translation_key == "write_rejected"

    after = hass.states.get(entity_id)
    snapshot.assert_match(_normalize_state(after))
