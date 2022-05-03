"""Test the Elro Connects siren platform."""
from __future__ import annotations

from unittest.mock import AsyncMock

from elro.command import Command
import pytest

from homeassistant.components import siren
from homeassistant.components.elro_connects.const import DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .test_common import MOCK_DEVICE_STATUS_DATA


@pytest.mark.parametrize(
    "entity_id,name,state,icon,device_class",
    [
        (
            "siren.beganegrond",
            "Beganegrond",
            STATE_OFF,
            "mdi:fire-alert",
            "smoke",
        ),
        (
            "siren.eerste_etage",
            "Eerste etage",
            STATE_ON,
            "mdi:fire-alert",
            "smoke",
        ),
        (
            "siren.zolder",
            "Zolder",
            STATE_OFF,
            "mdi:fire-alert",
            "smoke",
        ),
        (
            "siren.corner",
            "Corner",
            STATE_UNKNOWN,
            "mdi:molecule-co",
            "carbon_monoxide",
        ),
    ],
)
async def test_setup_integration_with_siren_platform(
    hass: HomeAssistant,
    mock_k1_connector: dict[AsyncMock],
    mock_entry: ConfigEntry,
    entity_id: str,
    name: str,
    state: str,
    icon: str,
    device_class: str,
) -> None:
    """Test we can setup the integration with the siren platform."""
    mock_k1_connector["result"].return_value = MOCK_DEVICE_STATUS_DATA
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    # Check entity setup from connector data
    entity = hass.states.get(entity_id)
    attributes = entity.attributes

    assert entity.state == state
    assert attributes["friendly_name"] == name
    assert attributes["icon"] == icon
    assert attributes["device_class"] == device_class


async def test_alarm_testing(
    hass: HomeAssistant,
    mock_k1_connector: dict[AsyncMock],
    mock_entry: ConfigEntry,
) -> None:
    """Test we can start a test alarm and silence it."""
    entity_id = "siren.beganegrond"
    mock_k1_connector["result"].return_value = MOCK_DEVICE_STATUS_DATA
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    entity = hass.states.get(entity_id)
    assert entity.state == STATE_OFF

    # Turn siren on with test signal
    mock_k1_connector["result"].reset_mock()
    await hass.services.async_call(
        siren.DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )

    entity = hass.states.get(entity_id)
    assert entity.state == STATE_ON
    assert (
        mock_k1_connector["result"].call_args[0][0]["cmd_id"]
        == Command.EQUIPMENT_CONTROL
    )
    assert (
        mock_k1_connector["result"].call_args[0][0]["additional_attributes"][
            "device_status"
        ]
        == "17000000"
    )
    assert mock_k1_connector["result"].call_args[1] == {"device_ID": 1}

    # Turn siren off with silence command
    mock_k1_connector["result"].reset_mock()
    await hass.services.async_call(
        siren.DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )

    entity = hass.states.get(entity_id)
    assert entity.state == STATE_OFF
    assert (
        mock_k1_connector["result"].call_args[0][0]["cmd_id"]
        == Command.EQUIPMENT_CONTROL
    )
    assert (
        mock_k1_connector["result"].call_args[0][0]["additional_attributes"][
            "device_status"
        ]
        == "00000000"
    )
    assert mock_k1_connector["result"].call_args[1] == {"device_ID": 1}
