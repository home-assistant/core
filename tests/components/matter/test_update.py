"""Test Matter number entities."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

from chip.clusters import Objects as clusters
from chip.clusters.ClusterObjects import ClusterAttributeDescriptor
from freezegun.api import FrozenDateTimeFactory
from matter_server.client.models.node import MatterNode
from matter_server.common.errors import UpdateCheckError, UpdateError
from matter_server.common.models import MatterSoftwareVersion, UpdateSource
import pytest

from homeassistant.components.homeassistant import (
    DOMAIN as HA_DOMAIN,
    SERVICE_UPDATE_ENTITY,
)
from homeassistant.components.matter.update import SCAN_INTERVAL
from homeassistant.components.update import (
    ATTR_VERSION,
    DOMAIN as UPDATE_DOMAIN,
    SERVICE_INSTALL,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.restore_state import STORAGE_KEY as RESTORE_STATE_KEY
from homeassistant.setup import async_setup_component

from .common import (
    set_node_attribute,
    setup_integration_with_node_fixture,
    trigger_subscription_callback,
)

from tests.common import (
    async_fire_time_changed,
    async_mock_restore_state_shutdown_restart,
    mock_restore_cache_with_extra_data,
)

TEST_SOFTWARE_VERSION = MatterSoftwareVersion(
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
    """Fixture to check for node updates."""
    matter_client.check_node_update = AsyncMock(return_value=None)
    return matter_client.check_node_update


@pytest.fixture(name="update_node")
async def update_node_fixture(matter_client: MagicMock) -> AsyncMock:
    """Fixture to install update."""
    matter_client.update_node = AsyncMock(return_value=None)
    return matter_client.update_node


@pytest.mark.parametrize("node_fixture", ["dimmable_light"])
async def test_update_entity(
    hass: HomeAssistant,
    matter_client: MagicMock,
    check_node_update: AsyncMock,
    matter_node: MatterNode,
) -> None:
    """Test update entity exists and update check got made."""
    state = hass.states.get("update.mock_dimmable_light")
    assert state
    assert state.state == STATE_OFF

    assert matter_client.check_node_update.call_count == 1


@pytest.mark.parametrize("node_fixture", ["dimmable_light"])
async def test_update_check_service(
    hass: HomeAssistant,
    matter_client: MagicMock,
    check_node_update: AsyncMock,
    matter_node: MatterNode,
) -> None:
    """Test check device update through service call."""
    state = hass.states.get("update.mock_dimmable_light")
    assert state
    assert state.state == STATE_OFF
    assert state.attributes.get("installed_version") == "v1.0"

    await async_setup_component(hass, HA_DOMAIN, {})

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
        HA_DOMAIN,
        SERVICE_UPDATE_ENTITY,
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


@pytest.mark.parametrize("node_fixture", ["dimmable_light"])
async def test_update_install(
    hass: HomeAssistant,
    matter_client: MagicMock,
    check_node_update: AsyncMock,
    matter_node: MatterNode,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test device update with Matter attribute changes influence progress."""
    state = hass.states.get("update.mock_dimmable_light")
    assert state
    assert state.state == STATE_OFF
    assert state.attributes.get("installed_version") == "v1.0"

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

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert matter_client.check_node_update.call_count == 2

    state = hass.states.get("update.mock_dimmable_light")
    assert state
    assert state.state == STATE_ON
    assert state.attributes.get("latest_version") == "v2.0"
    assert (
        state.attributes.get("release_url")
        == "http://home-assistant.io/non-existing-product"
    )

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {
            ATTR_ENTITY_ID: "update.mock_dimmable_light",
        },
        blocking=True,
    )

    set_node_attribute_typed(
        matter_node,
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
        matter_node,
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
        matter_node,
        0,
        clusters.OtaSoftwareUpdateRequestor.Attributes.UpdateState,
        clusters.OtaSoftwareUpdateRequestor.Enums.UpdateStateEnum.kIdle,
    )
    set_node_attribute_typed(
        matter_node,
        0,
        clusters.BasicInformation.Attributes.SoftwareVersion,
        2,
    )
    set_node_attribute_typed(
        matter_node,
        0,
        clusters.BasicInformation.Attributes.SoftwareVersionString,
        "v2.0",
    )
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("update.mock_dimmable_light")
    assert state.state == STATE_OFF
    assert state.attributes.get("installed_version") == "v2.0"


@pytest.mark.parametrize("node_fixture", ["dimmable_light"])
async def test_update_install_failure(
    hass: HomeAssistant,
    matter_client: MagicMock,
    check_node_update: AsyncMock,
    update_node: AsyncMock,
    matter_node: MatterNode,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test update entity service call errors."""
    state = hass.states.get("update.mock_dimmable_light")
    assert state
    assert state.state == STATE_OFF
    assert state.attributes.get("installed_version") == "v1.0"

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

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert matter_client.check_node_update.call_count == 2

    state = hass.states.get("update.mock_dimmable_light")
    assert state
    assert state.state == STATE_ON
    assert state.attributes.get("latest_version") == "v2.0"
    assert (
        state.attributes.get("release_url")
        == "http://home-assistant.io/non-existing-product"
    )

    update_node.side_effect = UpdateCheckError("Error finding applicable update")

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {
                ATTR_ENTITY_ID: "update.mock_dimmable_light",
                ATTR_VERSION: "v3.0",
            },
            blocking=True,
        )

    update_node.side_effect = UpdateError("Error updating node")

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {
                ATTR_ENTITY_ID: "update.mock_dimmable_light",
                ATTR_VERSION: "v3.0",
            },
            blocking=True,
        )


@pytest.mark.parametrize("node_fixture", ["dimmable_light"])
async def test_update_state_save_and_restore(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    matter_client: MagicMock,
    check_node_update: AsyncMock,
    matter_node: MatterNode,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test latest update information is retained across reload/restart."""
    state = hass.states.get("update.mock_dimmable_light")
    assert state
    assert state.state == STATE_OFF
    assert state.attributes.get("installed_version") == "v1.0"

    check_node_update.return_value = TEST_SOFTWARE_VERSION

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert matter_client.check_node_update.call_count == 2

    state = hass.states.get("update.mock_dimmable_light")
    assert state
    assert state.state == STATE_ON
    assert state.attributes.get("latest_version") == "v2.0"
    await hass.async_block_till_done()
    await async_mock_restore_state_shutdown_restart(hass)

    assert len(hass_storage[RESTORE_STATE_KEY]["data"]) == 1
    state = hass_storage[RESTORE_STATE_KEY]["data"][0]["state"]
    assert state["entity_id"] == "update.mock_dimmable_light"
    extra_data = hass_storage[RESTORE_STATE_KEY]["data"][0]["extra_data"]

    # Check that the extra data has the format we expect.
    assert extra_data == {
        "software_update": {
            "vid": 65521,
            "pid": 32768,
            "software_version": 2,
            "software_version_string": "v2.0",
            "firmware_information": "",
            "min_applicable_software_version": 0,
            "max_applicable_software_version": 1,
            "release_notes_url": "http://home-assistant.io/non-existing-product",
            "update_source": "local",
        }
    }


async def test_update_state_restore(
    hass: HomeAssistant,
    matter_client: MagicMock,
    check_node_update: AsyncMock,
    update_node: AsyncMock,
) -> None:
    """Test latest update information extra data is restored."""
    mock_restore_cache_with_extra_data(
        hass,
        (
            (
                State(
                    "update.mock_dimmable_light",
                    STATE_ON,
                    {
                        "auto_update": False,
                        "installed_version": "v1.0",
                        "in_progress": False,
                        "latest_version": "v2.0",
                    },
                ),
                {"software_update": TEST_SOFTWARE_VERSION.as_dict()},
            ),
        ),
    )
    await setup_integration_with_node_fixture(hass, "dimmable_light", matter_client)

    assert check_node_update.call_count == 0

    state = hass.states.get("update.mock_dimmable_light")
    assert state
    assert state.state == STATE_ON
    assert state.attributes.get("latest_version") == "v2.0"

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {
            ATTR_ENTITY_ID: "update.mock_dimmable_light",
        },
        blocking=True,
    )

    # Validate that the integer software version from the extra data is passed
    # to the update_node call.
    assert update_node.call_count == 1
    assert (
        update_node.call_args[1]["software_version"]
        == TEST_SOFTWARE_VERSION.software_version
    )
