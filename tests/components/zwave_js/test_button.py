"""Test the Z-Wave JS button entities."""

from datetime import timedelta
from unittest.mock import MagicMock

import pytest
from zwave_js_server.model.node import Node

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.zwave_js.const import DOMAIN, SERVICE_REFRESH_VALUE
from homeassistant.components.zwave_js.helpers import get_valueless_base_unique_id
from homeassistant.config_entries import RELOAD_AFTER_UPDATE_DELAY
from homeassistant.const import ATTR_ENTITY_ID, EntityCategory, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.fixture
def platforms() -> list[str]:
    """Fixture to specify platforms to test."""
    return [Platform.BUTTON]


async def test_ping_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    client,
    climate_radio_thermostat_ct100_plus_different_endpoints,
    integration,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test ping entity."""
    client.async_send_command.return_value = {"responded": True}

    # Test successful ping call
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {
            ATTR_ENTITY_ID: "button.z_wave_thermostat_ping",
        },
        blocking=True,
    )
    await hass.async_block_till_done()
    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args_list[0][0][0]
    assert args["command"] == "node.ping"
    assert (
        args["nodeId"]
        == climate_radio_thermostat_ct100_plus_different_endpoints.node_id
    )

    client.async_send_command.reset_mock()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_REFRESH_VALUE,
        {
            ATTR_ENTITY_ID: "button.z_wave_thermostat_ping",
        },
        blocking=True,
    )
    await hass.async_block_till_done()
    assert "There is no value to refresh for this entity" in caplog.text

    # Assert a node ping button entity is not created for the controller
    driver = client.driver
    node = driver.controller.nodes[1]
    assert node.is_controller_node
    assert (
        entity_registry.async_get_entity_id(
            DOMAIN, "sensor", f"{get_valueless_base_unique_id(driver, node)}.ping"
        )
        is None
    )


async def test_notification_idle_button(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    client: MagicMock,
    multisensor_6: Node,
    integration: MockConfigEntry,
) -> None:
    """Test Notification idle button."""
    node = multisensor_6
    entity_id = "button.multisensor_6_idle_home_security_cover_status"
    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry
    assert entity_entry.entity_category is EntityCategory.CONFIG
    assert entity_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert hass.states.get(entity_id) is None  # disabled by default

    entity_registry.async_update_entity(
        entity_id,
        disabled_by=None,
    )
    async_fire_time_changed(
        hass,
        dt_util.utcnow() + timedelta(seconds=RELOAD_AFTER_UPDATE_DELAY + 1),
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "unknown"
    assert (
        state.attributes["friendly_name"]
        == "Multisensor 6 Idle Home Security Cover status"
    )

    # Test successful idle call
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {
            ATTR_ENTITY_ID: entity_id,
        },
        blocking=True,
    )

    assert client.async_send_command_no_wait.call_count == 1
    args = client.async_send_command_no_wait.call_args[0][0]
    assert args["command"] == "node.manually_idle_notification_value"
    assert args["nodeId"] == node.node_id
    assert args["valueId"] == {
        "commandClass": 113,
        "endpoint": 0,
        "property": "Home Security",
        "propertyKey": "Cover status",
    }
