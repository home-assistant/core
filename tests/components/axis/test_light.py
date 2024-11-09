"""Axis light platform tests."""

from typing import Any
from unittest.mock import patch

from axis.models.api import CONTEXT
import pytest
import respx
from syrupy import SnapshotAssertion

from homeassistant.components.light import ATTR_BRIGHTNESS, DOMAIN as LIGHT_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import ConfigEntryFactoryType, RtspEventMock
from .const import DEFAULT_HOST, NAME

from tests.common import snapshot_platform

API_DISCOVERY_LIGHT_CONTROL = {
    "id": "light-control",
    "version": "1.1",
    "name": "Light Control",
}


@pytest.fixture
def light_control_items() -> list[dict[str, Any]]:
    """Available lights."""
    return [
        {
            "lightID": "led0",
            "lightType": "IR",
            "enabled": True,
            "synchronizeDayNightMode": True,
            "lightState": False,
            "automaticIntensityMode": False,
            "automaticAngleOfIlluminationMode": False,
            "nrOfLEDs": 1,
            "error": False,
            "errorInfo": "",
        }
    ]


@pytest.fixture(autouse=True)
def light_control_fixture(light_control_items: list[dict[str, Any]]) -> None:
    """Light control mock response."""
    data = {
        "apiVersion": "1.1",
        "context": CONTEXT,
        "method": "getLightInformation",
        "data": {"items": light_control_items},
    }
    respx.post(
        f"http://{DEFAULT_HOST}:80/axis-cgi/lightcontrol.cgi",
        json={
            "apiVersion": "1.1",
            "context": CONTEXT,
            "method": "getLightInformation",
        },
    ).respond(
        json=data,
    )


@pytest.mark.parametrize("api_discovery_items", [API_DISCOVERY_LIGHT_CONTROL])
@pytest.mark.parametrize("light_control_items", [[]])
@pytest.mark.usefixtures("config_entry_setup")
async def test_no_light_entity_without_light_control_representation(
    hass: HomeAssistant,
    mock_rtsp_event: RtspEventMock,
) -> None:
    """Verify no lights entities get created without light control representation."""
    mock_rtsp_event(
        topic="tns1:Device/tnsaxis:Light/Status",
        data_type="state",
        data_value="ON",
        source_name="id",
        source_idx="0",
    )
    await hass.async_block_till_done()

    assert not hass.states.async_entity_ids(LIGHT_DOMAIN)


@pytest.mark.parametrize("api_discovery_items", [API_DISCOVERY_LIGHT_CONTROL])
async def test_lights(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    config_entry_factory: ConfigEntryFactoryType,
    mock_rtsp_event: RtspEventMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that lights are loaded properly."""
    # Add light
    respx.post(
        f"http://{DEFAULT_HOST}:80/axis-cgi/lightcontrol.cgi",
        json={
            "apiVersion": "1.1",
            "context": CONTEXT,
            "method": "getCurrentIntensity",
            "params": {"lightID": "led0"},
        },
    ).respond(
        json={
            "apiVersion": "1.1",
            "context": "Axis library",
            "method": "getCurrentIntensity",
            "data": {"intensity": 100},
        },
    )
    respx.post(
        f"http://{DEFAULT_HOST}:80/axis-cgi/lightcontrol.cgi",
        json={
            "apiVersion": "1.1",
            "context": CONTEXT,
            "method": "getValidIntensity",
            "params": {"lightID": "led0"},
        },
    ).respond(
        json={
            "apiVersion": "1.1",
            "context": "Axis library",
            "method": "getValidIntensity",
            "data": {"ranges": [{"low": 0, "high": 150}]},
        },
    )

    with patch("homeassistant.components.axis.PLATFORMS", [Platform.LIGHT]):
        config_entry = await config_entry_factory()

    mock_rtsp_event(
        topic="tns1:Device/tnsaxis:Light/Status",
        data_type="state",
        data_value="ON",
        source_name="id",
        source_idx="0",
    )
    await hass.async_block_till_done()
    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)

    entity_id = f"{LIGHT_DOMAIN}.{NAME}_ir_light_0"

    # Turn on, set brightness, light already on
    with (
        patch("axis.interfaces.vapix.LightHandler.activate_light") as mock_activate,
        patch(
            "axis.interfaces.vapix.LightHandler.set_manual_intensity"
        ) as mock_set_intensity,
    ):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 50},
            blocking=True,
        )
        mock_activate.assert_not_awaited()
        mock_set_intensity.assert_called_once_with("led0", 29)

    # Turn off
    with patch(
        "axis.interfaces.vapix.LightHandler.deactivate_light"
    ) as mock_deactivate:
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        mock_deactivate.assert_called_once()

    # Event turn off light
    mock_rtsp_event(
        topic="tns1:Device/tnsaxis:Light/Status",
        data_type="state",
        data_value="OFF",
        source_name="id",
        source_idx="0",
    )
    await hass.async_block_till_done()

    light_0 = hass.states.get(entity_id)
    assert light_0.state == STATE_OFF

    # Turn on, set brightness
    with (
        patch("axis.interfaces.vapix.LightHandler.activate_light") as mock_activate,
        patch(
            "axis.interfaces.vapix.LightHandler.set_manual_intensity"
        ) as mock_set_intensity,
    ):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        mock_activate.assert_called_once()
        mock_set_intensity.assert_not_called()

    # Turn off, light already off
    with patch(
        "axis.interfaces.vapix.LightHandler.deactivate_light"
    ) as mock_deactivate:
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        mock_deactivate.assert_not_called()
