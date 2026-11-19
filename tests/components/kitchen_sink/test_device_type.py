"""Test the device types of the Everything but the Kitchen Sink devices."""

from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.kitchen_sink import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_type import async_get_bound_device_type
from homeassistant.setup import async_setup_component


@pytest.fixture(
    autouse=True,
    params=[
        pytest.param((Platform.SWITCH, Platform.SENSOR), id="switch_first"),
        pytest.param((Platform.SENSOR, Platform.SWITCH), id="sensor_first"),
    ],
)
async def setup_comp(hass: HomeAssistant, request: pytest.FixtureRequest) -> None:
    """Set up the kitchen sink with its switches and sensors, one platform first."""
    first, second = request.param
    with patch(
        "homeassistant.components.kitchen_sink.COMPONENTS_WITH_DEMO_PLATFORM",
        [first],
    ):
        assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
        await hass.async_block_till_done()
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    await hass.config_entries.async_forward_entry_setups(entry, [second])
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    "entity_id",
    [
        pytest.param("switch.smart_plug", id="smart_plug"),
        pytest.param("switch.hub_switch", id="untyped_device"),
        pytest.param("switch.power_strip_with_2_sockets_outlet_1", id="child_device"),
    ],
)
async def test_device_type(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    entity_id: str,
) -> None:
    """Test the type of the device of a switch and the entities filling its slots."""
    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry is not None
    assert entity_entry.device_id is not None
    device = device_registry.async_get(entity_entry.device_id)

    bound = async_get_bound_device_type(hass, entity_entry.device_id)

    assert bound is not None
    assert bound.device == device
    assert bound.missing_required == frozenset()
    assert {
        "type_id": bound.device_type.type_id,
        "slots": dict(bound.entity_ids),
    } == snapshot(name="device_type")
    assert device == snapshot(name="device")
