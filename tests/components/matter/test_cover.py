"""Test Matter covers."""
from unittest.mock import MagicMock, call

from chip.clusters import Objects as clusters
from matter_server.client.models.node import MatterNode
import pytest

from homeassistant.components.cover import (
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
)
from homeassistant.core import HomeAssistant

from .common import (
    set_node_attribute,
    setup_integration_with_node_fixture,
    trigger_subscription_callback,
)


@pytest.fixture(name="window_covering")
async def window_covering_fixture(
    hass: HomeAssistant, matter_client: MagicMock
) -> MatterNode:
    """Fixture for a window covering node."""
    return await setup_integration_with_node_fixture(
        hass, "window-covering", matter_client
    )


# This tests needs to be adjusted to remove lingering tasks
@pytest.mark.parametrize("expected_lingering_tasks", [True])
async def test_cover(
    hass: HomeAssistant,
    matter_client: MagicMock,
    window_covering: MatterNode,
) -> None:
    """Test window covering."""
    await hass.services.async_call(
        "cover",
        "close_cover",
        {
            "entity_id": "cover.longan_link_wncv_da01",
        },
        blocking=True,
    )

    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=window_covering.node_id,
        endpoint_id=1,
        command=clusters.WindowCovering.Commands.DownOrClose(),
    )
    matter_client.send_device_command.reset_mock()

    await hass.services.async_call(
        "cover",
        "stop_cover",
        {
            "entity_id": "cover.longan_link_wncv_da01",
        },
        blocking=True,
    )

    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=window_covering.node_id,
        endpoint_id=1,
        command=clusters.WindowCovering.Commands.StopMotion(),
    )
    matter_client.send_device_command.reset_mock()

    await hass.services.async_call(
        "cover",
        "open_cover",
        {
            "entity_id": "cover.longan_link_wncv_da01",
        },
        blocking=True,
    )

    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=window_covering.node_id,
        endpoint_id=1,
        command=clusters.WindowCovering.Commands.UpOrOpen(),
    )
    matter_client.send_device_command.reset_mock()

    await hass.services.async_call(
        "cover",
        "set_cover_position",
        {
            "entity_id": "cover.longan_link_wncv_da01",
            "position": 50,
        },
        blocking=True,
    )

    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=window_covering.node_id,
        endpoint_id=1,
        command=clusters.WindowCovering.Commands.GoToLiftPercentage(5000),
    )
    matter_client.send_device_command.reset_mock()

    set_node_attribute(window_covering, 1, 258, 8, 30)
    set_node_attribute(window_covering, 1, 258, 10, 2)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("cover.longan_link_wncv_da01")
    assert state
    assert state.state == STATE_CLOSING

    set_node_attribute(window_covering, 1, 258, 8, 0)
    set_node_attribute(window_covering, 1, 258, 10, 0)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("cover.longan_link_wncv_da01")
    assert state
    assert state.state == STATE_OPEN

    set_node_attribute(window_covering, 1, 258, 8, 50)
    set_node_attribute(window_covering, 1, 258, 10, 1)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("cover.longan_link_wncv_da01")
    assert state
    assert state.state == STATE_OPENING

    set_node_attribute(window_covering, 1, 258, 8, 100)
    set_node_attribute(window_covering, 1, 258, 10, 0)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("cover.longan_link_wncv_da01")
    assert state
    assert state.attributes["current_position"] == 0
    assert state.state == STATE_CLOSED
