"""Tests for the proprietary Eve Thermo schedule status decoder."""

import base64
from unittest.mock import MagicMock

from matter_server.client.models.node import MatterNode
import pytest

from homeassistant.components.matter.binary_sensor import _eve_thermo_schedule_enabled
from homeassistant.core import HomeAssistant

from .common import set_node_attribute_and_notify


@pytest.mark.parametrize(
    ("flag", "expected"),
    [(0x0C, False), (0x0D, True), (0x0E, False), (0x0F, True)],
)
def test_eve_thermo_schedule_flag(flag: int, expected: bool) -> None:
    """Only the low bit of the observed configuration byte determines state."""
    payload = bytearray(275)
    payload[211] = flag
    assert _eve_thermo_schedule_enabled(bytes(payload)) is expected
    assert _eve_thermo_schedule_enabled(base64.b64encode(payload).decode()) is expected


@pytest.mark.parametrize(
    "payload", [b"", b"invalid", bytes(274), bytes(276), "not base64!", 42]
)
def test_eve_thermo_schedule_invalid(payload: bytes | str | int) -> None:
    """Unknown payload formats must not report a false off state."""
    assert _eve_thermo_schedule_enabled(payload) is None


@pytest.fixture
def attributes() -> dict[str, str]:
    """Provide the observed size of the proprietary configuration."""
    payload = bytearray(275)
    payload[211] = 12
    return {"1/319486977/319422464": base64.b64encode(payload).decode()}


@pytest.mark.parametrize("node_fixture", ["eve_thermo_v4"])
async def test_schedule_entity(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Check discovery and state updates via Matter events."""
    entity_id = "binary_sensor.eve_thermo_20ebp1701_heating_schedule"
    assert hass.states.get(entity_id).state == "off"

    for flag, expected in ((13, "on"), (12, "off")):
        payload = bytearray(275)
        payload[211] = flag
        await set_node_attribute_and_notify(
            hass,
            matter_client,
            matter_node,
            endpoint=1,
            cluster_id=0x130AFC01,
            attribute_id=0x130A0000,
            value=base64.b64encode(payload).decode(),
        )
        assert hass.states.get(entity_id).state == expected

    await set_node_attribute_and_notify(
        hass,
        matter_client,
        matter_node,
        endpoint=1,
        cluster_id=0x130AFC01,
        attribute_id=0x130A0000,
        value=base64.b64encode(bytes(274)).decode(),
    )
    assert hass.states.get(entity_id).state == "unknown"
