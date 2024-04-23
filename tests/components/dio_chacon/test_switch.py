"""Test the Dio Chacon Switch sensor."""

import logging
from unittest.mock import patch

from dio_chacon_wifi_api import DIOChaconAPIClient
from dio_chacon_wifi_api.const import DeviceTypeEnum

from homeassistant.components.dio_chacon.const import DOMAIN
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    CONF_PASSWORD,
    CONF_UNIQUE_ID,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry

_LOGGER = logging.getLogger(__name__)

MOCK_SWITCH_DEVICE = {
    "L4HActuator_idmock1": {
        "id": "L4HActuator_idmock1",
        "name": "Switch mock 1",
        "type": "LIGHT_SWITCH",
        "model": "CERNwd-3B_1.0.6",
        "connected": True,
        "is_on": True,
    }
}


async def test_switch(hass: HomeAssistant, entity_registry: er.EntityRegistry) -> None:
    """Test the creation and values of the Dio Chacon switch."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test_entry_unique_id",
        data={
            CONF_USERNAME: "dummylogin",
            CONF_PASSWORD: "dummypass",
            CONF_UNIQUE_ID: "dummy-user-id",
        },
    )

    entry.add_to_hass(hass)

    def mock_side_effect(*args, **kwargs):
        if kwargs["device_type_to_search"] == [
            DeviceTypeEnum.SWITCH_LIGHT,
            DeviceTypeEnum.SWITCH_PLUG,
        ]:
            return MOCK_SWITCH_DEVICE
        return None

    with patch(
        "dio_chacon_wifi_api.DIOChaconAPIClient.search_all_devices",
        side_effect=mock_side_effect,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    entity = entity_registry.async_get("switch.switch_mock_1")
    _LOGGER.debug("Entity switch mock registered : %s", entity)
    assert entity.unique_id == "L4HActuator_idmock1"
    assert entity.entity_id == "switch.switch_mock_1"

    state = hass.states.get("switch.switch_mock_1")
    _LOGGER.debug(
        "Entity switch mock state : %s and mock state attributes : %s",
        state,
        state.attributes,
    )

    assert state
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Switch mock 1"

    with patch(
        "dio_chacon_wifi_api.DIOChaconAPIClient.switch_switch",
    ):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: entity.entity_id},
            blocking=True,
        )
        await hass.async_block_till_done()
        state = hass.states.get("switch.switch_mock_1")
        assert state.state == STATE_ON  # is on

        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: entity.entity_id},
            blocking=True,
        )
        await hass.async_block_till_done()
        state = hass.states.get("switch.switch_mock_1")
        assert (
            state.state == STATE_ON
        )  # turn off does not change directly the state, it is made by a server side callback.

    # Server side callback tests
    client: DIOChaconAPIClient = hass.data[DOMAIN][entry.entry_id]
    client._callback_device_state(
        {"id": "L4HActuator_idmock1", "connected": True, "is_on": False}
    )
    await hass.async_block_till_done()
    state = hass.states.get("switch.switch_mock_1")
    assert state
    assert state.state == "off"  # is off

    # reload state service test :
    with patch(
        "dio_chacon_wifi_api.DIOChaconAPIClient.get_status_details",
        return_value={"L4HActuator_idmock1": {"connected": True, "is_on": True}},
    ):
        await hass.services.async_call(
            DOMAIN, "reload_state", {ATTR_ENTITY_ID: entity.entity_id}, blocking=True
        )
        await hass.async_block_till_done()
        state = hass.states.get("switch.switch_mock_1")
        assert state.state == STATE_ON  # is on

    # pytest.fail("Fails to display logs of tests")


async def test_no_switch_found(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test the switch absence."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test_entry_unique_id",
        data={
            CONF_USERNAME: "dummylogin",
            CONF_PASSWORD: "dummypass",
            CONF_UNIQUE_ID: "dummy-user-id",
        },
    )

    entry.add_to_hass(hass)

    with patch(
        "dio_chacon_wifi_api.DIOChaconAPIClient.search_all_devices",
        return_value=None,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    entity = entity_registry.async_get("switch.switch_mock_1")
    _LOGGER.debug("Entity switch mock not found : %s", entity)
    assert not entity
