"""Test Matter number entities."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

from chip.clusters import Objects as clusters
from chip.clusters.ClusterObjects import ClusterAttributeDescriptor
from matter_server.client.models.node import MatterNode
from matter_server.common.models import MatterSoftwareVersion, UpdateSource
import pytest

from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .common import (
    set_node_attribute,
    setup_integration_with_node_fixture,
    trigger_subscription_callback,
)


def set_node_attribute_typed(
    node: MatterNode,
    endpoint: int,
    attribute: ClusterAttributeDescriptor,
    value: Any,
) -> None:
    """Set a node attribute."""
    set_node_attribute(
        node, endpoint, attribute.cluster_id, attribute.attribute_id, value
    )


@pytest.fixture(name="check_node_update")
async def check_node_update_fixture(matter_client: MagicMock) -> AsyncMock:
    """Fixture for a flow sensor node."""
    matter_client.check_node_update = AsyncMock(return_value=None)
    return matter_client.check_node_update


@pytest.fixture(name="updateable_node")
async def updateable_node_fixture(
    hass: HomeAssistant, matter_client: MagicMock
) -> MatterNode:
    """Fixture for a flow sensor node."""
    return await setup_integration_with_node_fixture(
        hass, "dimmable-light", matter_client
    )


async def test_update_entity(
    hass: HomeAssistant,
    matter_client: MagicMock,
    check_node_update: AsyncMock,
    updateable_node: MatterNode,
) -> None:
    """Test update entity exists and update check got made."""
    state = hass.states.get("update.mock_dimmable_light")
    assert state
    assert state.state == STATE_OFF

    assert matter_client.check_node_update.call_count == 1


async def test_update_install(
    hass: HomeAssistant,
    matter_client: MagicMock,
    check_node_update: AsyncMock,
    updateable_node: MatterNode,
) -> None:
    """Test update entity exists and update check got made."""
    state = hass.states.get("update.mock_dimmable_light")
    assert state
    assert state.state == STATE_OFF
    assert state.attributes.get("installed_version") == "v1.0"

    await async_setup_component(hass, "homeassistant", {})

    check_node_update.return_value = MatterSoftwareVersion(
        vid=65521,
        pid=32768,
        software_version=2,
        software_version_string="v2.0",
        firmware_information="",
        min_applicable_software_version=0,
        max_applicable_software_version=1,
        release_notes_url="http://home-assistant.io/non-existing-product",
        update_source=UpdateSource.LOCAL,
    )

    await hass.services.async_call(
        "homeassistant",
        "update_entity",
        {
            ATTR_ENTITY_ID: "update.mock_dimmable_light",
        },
        blocking=True,
    )

    assert matter_client.check_node_update.call_count == 2

    state = hass.states.get("update.mock_dimmable_light")
    assert state
    assert state.state == STATE_ON
    assert state.attributes.get("latest_version") == "v2.0"
    assert (
        state.attributes.get("release_url")
        == "http://home-assistant.io/non-existing-product"
    )

    await async_setup_component(hass, "update", {})

    await hass.services.async_call(
        "update",
        "install",
        {
            ATTR_ENTITY_ID: "update.mock_dimmable_light",
        },
        blocking=True,
    )

    set_node_attribute_typed(
        updateable_node,
        0,
        clusters.OtaSoftwareUpdateRequestor.Attributes.UpdateState,
        clusters.OtaSoftwareUpdateRequestor.Enums.UpdateStateEnum.kDownloading,
    )
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("update.mock_dimmable_light")
    assert state
    assert state.state == STATE_ON
    assert state.attributes.get("in_progress")

    set_node_attribute_typed(
        updateable_node,
        0,
        clusters.OtaSoftwareUpdateRequestor.Attributes.UpdateStateProgress,
        50,
    )
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("update.mock_dimmable_light")
    assert state
    assert state.state == STATE_ON
    assert state.attributes.get("in_progress") == 50

    set_node_attribute_typed(
        updateable_node,
        0,
        clusters.OtaSoftwareUpdateRequestor.Attributes.UpdateState,
        clusters.OtaSoftwareUpdateRequestor.Enums.UpdateStateEnum.kIdle,
    )
    set_node_attribute_typed(
        updateable_node,
        0,
        clusters.BasicInformation.Attributes.SoftwareVersion,
        2,
    )
    set_node_attribute_typed(
        updateable_node,
        0,
        clusters.BasicInformation.Attributes.SoftwareVersionString,
        "v2.0",
    )
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("update.mock_dimmable_light")
    assert state.state == STATE_OFF
    assert state.attributes.get("installed_version") == "v2.0"
