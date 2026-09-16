"""Test the Eurotronic Comet WiFi config flow."""

from unittest.mock import AsyncMock

import pytest

from homeassistant.components.eurotronic_comet_wifi.const import DOMAIN
from homeassistant.components.mqtt import MQTT_CONNECTION_STATE
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_MAC
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.dispatcher import async_dispatcher_send

from . import COMMAND_TOPIC_REQUEST, MAC
from .conftest import FakeDevice

from tests.common import MockConfigEntry
from tests.typing import MqttMockHAClient

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_form(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    device: FakeDevice,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test a thermostat that answers is added with its normalized MAC address."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_MAC: "aa:bb:cc:dd:ee:ff"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Comet WiFi {MAC}"
    assert result["data"] == {CONF_MAC: MAC}
    assert result["result"].unique_id == MAC
    assert len(mock_setup_entry.mock_calls) == 1
    # The flow asked the thermostat for its values.
    published_topics = [call.args[0] for call in mqtt_mock.async_publish.mock_calls]
    assert COMMAND_TOPIC_REQUEST in published_topics


async def test_form_cannot_connect(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient, device: FakeDevice
) -> None:
    """Test a silent thermostat is reported, and the flow recovers."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    device.online = False
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_MAC: MAC}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    device.online = True
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_MAC: MAC}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("device")
async def test_form_invalid_mac(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Test a malformed MAC address is reported, and the flow recovers."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_MAC: "not-a-mac"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_MAC: "invalid_mac"}
    # Nothing was sent to the thermostat.
    published_topics = [call.args[0] for call in mqtt_mock.async_publish.mock_calls]
    assert not [topic for topic in published_topics if topic.startswith("01/")]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_MAC: MAC}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mqtt_mock", "device")
async def test_form_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test a thermostat cannot be added twice."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_MAC: "aa-bb-cc-dd-ee-ff"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_form_mqtt_not_connected(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Test the flow aborts when MQTT is not connected to a broker."""
    mqtt_mock.connected = False
    async_dispatcher_send(hass, MQTT_CONNECTION_STATE, False)
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "mqtt_not_connected"


async def test_form_mqtt_not_configured(hass: HomeAssistant) -> None:
    """Test the flow aborts when the MQTT integration is not set up."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "mqtt_not_configured"
