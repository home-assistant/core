"""Tests for the arwn config flow."""

from homeassistant import config_entries
from homeassistant.components.arwn.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.mqtt import MqttServiceInfo

from tests.typing import MqttMockHAClient


async def test_user_step(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
) -> None:
    """Test the user step shows confirm form then creates entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"

    config_result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert config_result["type"] is FlowResultType.CREATE_ENTRY
    assert config_result["title"] == "Ambient Radio Weather Network"


async def test_mqtt_step(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
) -> None:
    """Test that MQTT discovery triggers a confirm form."""
    discovery_info = MqttServiceInfo(
        topic="arwn/temperature/outside",
        payload='{"temp": 72.5, "units": "F"}',
        qos=0,
        retain=False,
        subscribed_topic="arwn/#",
        timestamp=0.0,
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_MQTT},
        data=discovery_info,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"


async def test_single_instance_allowed(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
) -> None:
    """Test that a second setup attempt is aborted."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    await hass.config_entries.flow.async_configure(result["flow_id"], user_input={})

    duplicate = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert duplicate["type"] is FlowResultType.ABORT
    assert duplicate["reason"] == "single_instance_allowed"
