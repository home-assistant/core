"""Test Alexa entity representation."""

from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components import fan, humidifier, remote, water_heater
from homeassistant.components.alexa import smart_home
from homeassistant.const import EntityCategory, UnitOfTemperature, __version__
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .test_common import get_default_config, get_new_request


async def test_unsupported_domain(hass: HomeAssistant) -> None:
    """Discovery ignores entities of unknown domains."""
    request = get_new_request("Alexa.Discovery", "Discover")

    hass.states.async_set("woz.boop", "on", {"friendly_name": "Boop Woz"})

    msg = await smart_home.async_handle_message(hass, get_default_config(hass), request)

    assert "event" in msg
    msg = msg["event"]

    assert not msg["payload"]["endpoints"]


async def test_categorized_hidden_entities(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Discovery ignores hidden and categorized entities."""
    request = get_new_request("Alexa.Discovery", "Discover")

    entity_entry1 = entity_registry.async_get_or_create(
        "switch",
        "test",
        "switch_config_id",
        suggested_object_id="config_switch",
        entity_category=EntityCategory.CONFIG,
    )
    entity_entry2 = entity_registry.async_get_or_create(
        "switch",
        "test",
        "switch_diagnostic_id",
        suggested_object_id="diagnostic_switch",
        entity_category=EntityCategory.DIAGNOSTIC,
    )
    entity_entry3 = entity_registry.async_get_or_create(
        "switch",
        "test",
        "switch_hidden_integration_id",
        suggested_object_id="hidden_integration_switch",
        hidden_by=er.RegistryEntryHider.INTEGRATION,
    )
    entity_entry4 = entity_registry.async_get_or_create(
        "switch",
        "test",
        "switch_hidden_user_id",
        suggested_object_id="hidden_user_switch",
        hidden_by=er.RegistryEntryHider.USER,
    )

    # These should not show up in the sync request
    hass.states.async_set(entity_entry1.entity_id, "on")
    hass.states.async_set(entity_entry2.entity_id, "something_else")
    hass.states.async_set(entity_entry3.entity_id, "blah")
    hass.states.async_set(entity_entry4.entity_id, "foo")

    msg = await smart_home.async_handle_message(hass, get_default_config(hass), request)

    assert "event" in msg
    msg = msg["event"]

    assert not msg["payload"]["endpoints"]


async def test_serialize_discovery(hass: HomeAssistant) -> None:
    """Test we can serialize a discovery."""
    request = get_new_request("Alexa.Discovery", "Discover")

    hass.states.async_set("switch.bla", "on", {"friendly_name": "Boop Woz"})

    msg = await smart_home.async_handle_message(hass, get_default_config(hass), request)

    assert "event" in msg
    msg = msg["event"]
    endpoint = msg["payload"]["endpoints"][0]

    assert endpoint["additionalAttributes"] == {
        "manufacturer": "Home Assistant",
        "model": "switch",
        "softwareVersion": __version__,
        "customIdentifier": "mock-user-id-switch.bla",
    }


async def test_serialize_discovery_partly_fails(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test we can partly serialize a discovery."""

    async def _mock_discovery() -> dict[str, Any]:
        request = get_new_request("Alexa.Discovery", "Discover")
        hass.states.async_set("switch.bla", "on", {"friendly_name": "My Switch"})
        hass.states.async_set("fan.bla", "on", {"friendly_name": "My Fan"})
        hass.states.async_set(
            "humidifier.bla", "on", {"friendly_name": "My Humidifier"}
        )
        hass.states.async_set(
            "sensor.bla",
            "20.1",
            {
                "friendly_name": "Livingroom temperature",
                "unit_of_measurement": UnitOfTemperature.CELSIUS,
                "device_class": "temperature",
            },
        )
        return await smart_home.async_handle_message(
            hass, get_default_config(hass), request
        )

    msg = await _mock_discovery()
    assert "event" in msg
    msg = msg["event"]
    assert len(msg["payload"]["endpoints"]) == 4
    endpoint_ids = {
        attributes["endpointId"] for attributes in msg["payload"]["endpoints"]
    }
    assert all(
        entity in endpoint_ids
        for entity in ("switch#bla", "fan#bla", "humidifier#bla", "sensor#bla")
    )

    # Simulate fetching the interfaces fails for fan entity
    with patch(
        "homeassistant.components.alexa.entities.FanCapabilities.interfaces",
        side_effect=TypeError(),
    ):
        msg = await _mock_discovery()
        assert "event" in msg
        msg = msg["event"]
        assert len(msg["payload"]["endpoints"]) == 3
        endpoint_ids = {
            attributes["endpointId"] for attributes in msg["payload"]["endpoints"]
        }
        assert all(
            entity in endpoint_ids
            for entity in ("switch#bla", "humidifier#bla", "sensor#bla")
        )
        assert "Unable to serialize fan.bla for discovery" in caplog.text
        caplog.clear()

    # Simulate serializing properties fails for sensor entity
    with patch(
        "homeassistant.components.alexa.entities.SensorCapabilities.default_display_categories",
        side_effect=ValueError(),
    ):
        msg = await _mock_discovery()
        assert "event" in msg
        msg = msg["event"]
        assert len(msg["payload"]["endpoints"]) == 3
        endpoint_ids = {
            attributes["endpointId"] for attributes in msg["payload"]["endpoints"]
        }
        assert all(
            entity in endpoint_ids
            for entity in ("switch#bla", "humidifier#bla", "fan#bla")
        )
        assert "Unable to serialize sensor.bla for discovery" in caplog.text
        caplog.clear()


async def test_serialize_discovery_recovers(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test we handle an interface raising unexpectedly during serialize discovery."""
    request = get_new_request("Alexa.Discovery", "Discover")

    hass.states.async_set("switch.bla", "on", {"friendly_name": "Boop Woz"})

    with patch(
        "homeassistant.components.alexa.capabilities.AlexaPowerController.serialize_discovery",
        side_effect=TypeError,
    ):
        msg = await smart_home.async_handle_message(
            hass, get_default_config(hass), request
        )

    assert "event" in msg
    msg = msg["event"]

    interfaces = {
        ifc["interface"] for ifc in msg["payload"]["endpoints"][0]["capabilities"]
    }

    assert "Alexa.PowerController" not in interfaces
    assert (
        "Error serializing Alexa.PowerController discovery"
        f" for {hass.states.get('switch.bla')}"
    ) in caplog.text


@pytest.mark.parametrize(
    ("domain", "state", "state_attributes", "mode_controller_exists"),
    [
        ("switch", "on", {}, False),
        (
            "fan",
            "on",
            {
                "preset_modes": ["eco", "auto"],
                "preset_mode": "eco",
                "supported_features": fan.FanEntityFeature.PRESET_MODE.value,
            },
            True,
        ),
        (
            "fan",
            "on",
            {
                "preset_modes": ["eco", "auto"],
                "preset_mode": None,
                "supported_features": fan.FanEntityFeature.PRESET_MODE.value,
            },
            True,
        ),
        (
            "fan",
            "on",
            {
                "preset_modes": ["eco"],
                "preset_mode": None,
                "supported_features": fan.FanEntityFeature.PRESET_MODE.value,
            },
            True,
        ),
        (
            "fan",
            "on",
            {
                "preset_modes": [],
                "preset_mode": None,
                "supported_features": fan.FanEntityFeature.PRESET_MODE.value,
            },
            False,
        ),
        (
            "humidifier",
            "on",
            {
                "available_modes": ["auto", "manual"],
                "mode": "auto",
                "supported_features": humidifier.HumidifierEntityFeature.MODES.value,
            },
            True,
        ),
        (
            "humidifier",
            "on",
            {
                "available_modes": ["auto"],
                "mode": None,
                "supported_features": humidifier.HumidifierEntityFeature.MODES.value,
            },
            True,
        ),
        (
            "humidifier",
            "on",
            {
                "available_modes": [],
                "mode": None,
                "supported_features": humidifier.HumidifierEntityFeature.MODES.value,
            },
            False,
        ),
        (
            "remote",
            "on",
            {
                "activity_list": ["tv", "dvd"],
                "current_activity": "tv",
                "supported_features": remote.RemoteEntityFeature.ACTIVITY.value,
            },
            True,
        ),
        (
            "remote",
            "on",
            {
                "activity_list": ["tv"],
                "current_activity": None,
                "supported_features": remote.RemoteEntityFeature.ACTIVITY.value,
            },
            True,
        ),
        (
            "remote",
            "on",
            {
                "activity_list": [],
                "current_activity": None,
                "supported_features": remote.RemoteEntityFeature.ACTIVITY.value,
            },
            False,
        ),
        (
            "water_heater",
            "on",
            {
                "operation_list": ["on", "auto"],
                "operation_mode": "auto",
                "supported_features": water_heater.WaterHeaterEntityFeature.OPERATION_MODE.value,
            },
            True,
        ),
        (
            "water_heater",
            "on",
            {
                "operation_list": ["on"],
                "operation_mode": None,
                "supported_features": water_heater.WaterHeaterEntityFeature.OPERATION_MODE.value,
            },
            True,
        ),
        (
            "water_heater",
            "on",
            {
                "operation_list": [],
                "operation_mode": None,
                "supported_features": water_heater.WaterHeaterEntityFeature.OPERATION_MODE.value,
            },
            False,
        ),
    ],
)
async def test_mode_controller_is_omitted_if_no_modes_are_set(
    hass: HomeAssistant,
    domain: str,
    state: str,
    state_attributes: dict[str, Any],
    mode_controller_exists: bool,
) -> None:
    """Test we do not generate an invalid discovery with AlexaModeController during serialize discovery.

    AlexModeControllers need at least 2 modes. If one mode is set, an extra mode will be added for compatibility.
    If no modes are offered, the mode controller should be omitted to prevent schema validations.
    """
    request = get_new_request("Alexa.Discovery", "Discover")

    hass.states.async_set(
        f"{domain}.bla", state, {"friendly_name": "Boop Woz"} | state_attributes
    )

    msg = await smart_home.async_handle_message(hass, get_default_config(hass), request)
    msg = msg["event"]

    interfaces = {
        ifc["interface"] for ifc in msg["payload"]["endpoints"][0]["capabilities"]
    }

    assert ("Alexa.ModeController" in interfaces) is mode_controller_exists
