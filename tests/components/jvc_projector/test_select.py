"""Tests for JVC Projector select platform."""

from unittest.mock import MagicMock

from jvcprojector import const

from homeassistant.components.select import (
    ATTR_OPTIONS,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_FRIENDLY_NAME, ATTR_OPTION
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry

INPUT_ENTITY_ID = "select.jvc_projector_input"


async def test_input_select(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_device: MagicMock,
    mock_integration: MockConfigEntry,
) -> None:
    """Test input select."""
    entity = hass.states.get(INPUT_ENTITY_ID)
    assert entity
    assert entity.attributes.get(ATTR_FRIENDLY_NAME) == "JVC Projector Input"
    assert entity.attributes.get(ATTR_OPTIONS) == [const.HDMI1, const.HDMI2]
    assert entity.state == const.HDMI1

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: INPUT_ENTITY_ID,
            ATTR_OPTION: const.HDMI2,
        },
        blocking=True,
    )

    mock_device.remote.assert_called_once_with(const.REMOTE_HDMI_2)
