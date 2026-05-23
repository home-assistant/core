"""Tests for ISY994 button platform."""

from unittest.mock import AsyncMock, MagicMock

from pyisy.constants import TAG_ENABLED
from pyisy.helpers import NodeProperty
from pyisy.nodes import Node
import pytest

from homeassistant.components.button import ButtonEntity
from homeassistant.components.isy994.button import (
    ISYNetworkResourceButtonEntity,
    ISYNodeBeepButtonEntity,
    ISYNodeButtonEntity,
    ISYNodeQueryButtonEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.helpers.device_registry import DeviceInfo


def make_device_info() -> DeviceInfo:
    """Return a minimal DeviceInfo."""
    return DeviceInfo(identifiers={("isy994", "test-device")})


def make_node(enabled: bool = True) -> MagicMock:
    """Return a minimal mock Node with TAG_ENABLED attribute."""
    node = MagicMock(spec=Node)
    setattr(node, TAG_ENABLED, enabled)
    node.address = "1 1"
    node.status_events = MagicMock()
    node.isy = MagicMock()
    node.isy.nodes = MagicMock()
    node.isy.nodes.status_events = MagicMock()
    node.isy.nodes.status_events.subscribe.return_value = MagicMock()
    return node


def make_button_entity(
    node: MagicMock | None = None,
    name: str = "Test",
    unique_id: str = "test_uid",
    entity_category: EntityCategory | None = None,
) -> ISYNodeButtonEntity:
    """Return an ISYNodeButtonEntity."""
    return ISYNodeButtonEntity(
        node=node or make_node(),
        name=name,
        unique_id=unique_id,
        device_info=make_device_info(),
        entity_category=entity_category,
    )


# ---------------------------------------------------------------------------
# ISYNodeButtonEntity.available
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("enabled", "expected"),
    [
        pytest.param(True, True, id="enabled"),
        pytest.param(False, False, id="disabled"),
    ],
)
def test_button_available(enabled: bool, expected: bool) -> None:
    """Available reflects the node's TAG_ENABLED attribute."""
    entity = make_button_entity(node=make_node(enabled=enabled))
    assert entity.available is expected


def test_button_available_defaults_true_when_no_tag() -> None:
    """Available defaults True when node has no TAG_ENABLED attribute."""
    node = MagicMock()
    del node.enabled
    entity = ISYNodeButtonEntity(
        node=node,
        name="Test",
        unique_id="uid",
        device_info=make_device_info(),
    )
    assert entity.available is True


# ---------------------------------------------------------------------------
# ISYNodeButtonEntity init attributes
# ---------------------------------------------------------------------------


def test_button_init_sets_attributes() -> None:
    """Constructor sets name, unique_id, entity_category, and device_info."""
    device_info = make_device_info()
    entity = ISYNodeButtonEntity(
        node=make_node(),
        name="Query",
        unique_id="some_uid_query",
        device_info=device_info,
        entity_category=EntityCategory.DIAGNOSTIC,
    )
    assert entity._attr_name == "Query"
    assert entity._attr_unique_id == "some_uid_query"
    assert entity._attr_entity_category is EntityCategory.DIAGNOSTIC
    assert entity._attr_device_info is device_info


# ---------------------------------------------------------------------------
# ISYNodeButtonEntity.async_on_update
# ---------------------------------------------------------------------------


def test_button_on_update_refreshes_enabled() -> None:
    """async_on_update re-reads TAG_ENABLED from the node."""
    node = make_node(enabled=True)
    entity = make_button_entity(node=node)
    entity.async_write_ha_state = MagicMock()

    setattr(node, TAG_ENABLED, False)
    event = MagicMock(spec=NodeProperty)
    entity.async_on_update(event, key="test")

    assert entity._node_enabled is False
    entity.async_write_ha_state.assert_called_once()


# ---------------------------------------------------------------------------
# ISYNodeQueryButtonEntity.async_press
# ---------------------------------------------------------------------------


async def test_query_button_press_calls_query() -> None:
    """async_press calls query() on the node."""
    node = make_node()
    node.query = AsyncMock()
    entity = ISYNodeQueryButtonEntity(
        node=node,
        name="Query",
        unique_id="uid_query",
        device_info=make_device_info(),
    )
    await entity.async_press()
    node.query.assert_awaited_once()


# ---------------------------------------------------------------------------
# ISYNodeBeepButtonEntity.async_press
# ---------------------------------------------------------------------------


async def test_beep_button_press_calls_beep() -> None:
    """async_press calls beep() on the node."""
    node = make_node()
    node.beep = AsyncMock()
    entity = ISYNodeBeepButtonEntity(
        node=node,
        name="Beep",
        unique_id="uid_beep",
        device_info=make_device_info(),
    )
    await entity.async_press()
    node.beep.assert_awaited_once()


# ---------------------------------------------------------------------------
# ISYNetworkResourceButtonEntity.async_press
# ---------------------------------------------------------------------------


async def test_network_resource_button_press_calls_run() -> None:
    """async_press calls run() on the network resource node."""
    node = MagicMock()
    node.run = AsyncMock()
    entity = ISYNetworkResourceButtonEntity(
        node=node,
        name="My Resource",
        unique_id="uid_net",
        device_info=make_device_info(),
    )
    await entity.async_press()
    node.run.assert_awaited_once()


def test_network_resource_button_has_entity_name_false() -> None:
    """ISYNetworkResourceButtonEntity sets _attr_has_entity_name = False."""
    node = MagicMock()
    entity = ISYNetworkResourceButtonEntity(
        node=node,
        name="My Resource",
        unique_id="uid_net",
        device_info=make_device_info(),
    )
    assert entity._attr_has_entity_name is False


# ---------------------------------------------------------------------------
# ISYNodeButtonEntity: ButtonEntity contract
# ---------------------------------------------------------------------------


def test_button_should_poll_false() -> None:
    """should_poll is False for all button entities."""
    entity = make_button_entity()
    assert entity.should_poll is False


def test_button_is_button_entity() -> None:
    """ISYNodeButtonEntity is a ButtonEntity subclass."""
    assert issubclass(ISYNodeButtonEntity, ButtonEntity)
