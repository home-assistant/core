"""Test config flow."""

from unittest.mock import MagicMock, patch

from qbusmqttapi.discovery import QbusDiscovery, QbusMqttDevice
from qbusmqttapi.state import QbusMqttGatewayState

from homeassistant.components.qbus.config_flow import QbusFlowHandler
from homeassistant.components.qbus.const import CONF_ID, CONF_SERIAL_NUMBER
from homeassistant.components.qbus.coordinator import QbusConfigCoordinator
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.mqtt import MqttServiceInfo


async def test_step_mqtt_empty_payload(
    qbus_config_flow: QbusFlowHandler,
    mqtt_discovery_info: MqttServiceInfo,
) -> None:
    """Test mqtt discovery with empty payload."""
    result = await qbus_config_flow.async_step_mqtt(mqtt_discovery_info)
    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "invalid_discovery_info"


async def test_step_mqtt_invalid_topic(
    qbus_config_flow: QbusFlowHandler,
    mqtt_discovery_info: MqttServiceInfo,
) -> None:
    """Test mqtt discovery with an invalid topic."""
    invalid_mqtt_info = mqtt_discovery_info
    invalid_mqtt_info.subscribed_topic = "invalid/topic"
    invalid_mqtt_info.payload = "{ }"

    result = await qbus_config_flow.async_step_mqtt(invalid_mqtt_info)
    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "invalid_discovery_info"


async def test_step_mqtt_calls_gateway(
    qbus_config_flow: QbusFlowHandler,
    mqtt_discovery_info_gateway: MqttServiceInfo,
) -> None:
    """Test if _async_handle_gateway_topic is called when subscribed_topic matches gateway."""

    with (
        patch.object(
            qbus_config_flow,
            "_async_handle_gateway_topic",
            return_value={"type": "abort"},
        ) as mock_gateway,
        patch.object(
            qbus_config_flow,
            "_async_handle_config_topic",
            return_value={"type": "abort"},
        ) as mock_config,
        patch.object(
            qbus_config_flow,
            "_async_handle_device_topic",
            return_value={"type": "abort"},
        ) as mock_device,
    ):
        await qbus_config_flow.async_step_mqtt(mqtt_discovery_info_gateway)

    mock_gateway.assert_called_once_with(mqtt_discovery_info_gateway)
    mock_config.assert_not_called()
    mock_device.assert_not_called()


async def test_step_mqtt_calls_config(
    qbus_config_flow: QbusFlowHandler,
    mqtt_discovery_info_config: MqttServiceInfo,
) -> None:
    """Test if _async_handle_gateway_topic is called when subscribed_topic matches config."""

    with (
        patch.object(
            qbus_config_flow,
            "_async_handle_gateway_topic",
            return_value={"type": "abort"},
        ) as mock_gateway,
        patch.object(
            qbus_config_flow,
            "_async_handle_config_topic",
            return_value={"type": "abort"},
        ) as mock_config,
        patch.object(
            qbus_config_flow,
            "_async_handle_device_topic",
            return_value={"type": "abort"},
        ) as mock_device,
    ):
        await qbus_config_flow.async_step_mqtt(mqtt_discovery_info_config)

    mock_gateway.assert_not_called()
    mock_config.assert_called_once_with(mqtt_discovery_info_config)
    mock_device.assert_not_called()


async def test_step_mqtt_calls_device(
    qbus_config_flow: QbusFlowHandler,
    mqtt_discovery_info_device: MqttServiceInfo,
) -> None:
    """Test if _async_handle_gateway_topic is called when subscribed_topic matches device."""

    with (
        patch.object(
            qbus_config_flow,
            "_async_handle_gateway_topic",
            return_value={"type": "abort"},
        ) as mock_gateway,
        patch.object(
            qbus_config_flow,
            "_async_handle_config_topic",
            return_value={"type": "abort"},
        ) as mock_config,
        patch.object(
            qbus_config_flow,
            "_async_handle_device_topic",
            return_value={"type": "abort"},
        ) as mock_device,
    ):
        await qbus_config_flow.async_step_mqtt(mqtt_discovery_info_device)

    mock_gateway.assert_not_called()
    mock_config.assert_not_called()
    mock_device.assert_called_once_with(mqtt_discovery_info_device)


async def test_handle_gateway_topic_when_online(
    qbus_config_flow: QbusFlowHandler,
    mqtt_discovery_info_gateway: MqttServiceInfo,
) -> None:
    """Test handling of gateway topic with payload indicating online."""
    with (
        patch.object(
            qbus_config_flow._message_factory,
            "parse_gateway_state",
            return_value=QbusMqttGatewayState({"online": True}),
        ),
        patch("homeassistant.components.mqtt.client.async_publish") as mock_publish,
    ):
        result = await qbus_config_flow._async_handle_gateway_topic(
            mqtt_discovery_info_gateway
        )

    assert mock_publish.called
    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "discovery_in_progress"


async def test_handle_gateway_topic_when_offline(
    qbus_config_flow: QbusFlowHandler,
    mqtt_discovery_info_gateway: MqttServiceInfo,
) -> None:
    """Test handling of gateway topic with payload indicating offline."""
    with (
        patch.object(
            qbus_config_flow._message_factory,
            "parse_gateway_state",
            return_value=QbusMqttGatewayState({"online": False}),
        ),
        patch("homeassistant.components.mqtt.client.async_publish") as mock_publish,
    ):
        result = await qbus_config_flow._async_handle_gateway_topic(
            mqtt_discovery_info_gateway
        )

    assert mock_publish.called is False
    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "discovery_in_progress"


async def test_handle_config_topic(
    qbus_config_flow: QbusFlowHandler,
    mqtt_discovery_info_config: MqttServiceInfo,
) -> None:
    """Test handling of config topic."""

    with (
        patch.object(
            qbus_config_flow._message_factory,
            "parse_discovery",
            return_value=QbusDiscovery({"devices": [], "app": "UbieLite"}),
        ),
        patch.object(
            QbusConfigCoordinator, "store_config", return_value=None, autospec=True
        ) as mock_store,
        patch("homeassistant.components.mqtt.client.async_publish") as mock_publish,
    ):
        result = await qbus_config_flow._async_handle_config_topic(
            mqtt_discovery_info_config
        )

    assert mock_store.called
    assert mock_publish.called
    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "discovery_in_progress"


async def test_handle_device_topic_success(
    qbus_config_flow: QbusFlowHandler, mqtt_discovery_info_device: MqttServiceInfo
) -> None:
    """Test handling of device topic."""

    mock_qbus_config = MagicMock(spec=QbusDiscovery)
    mock_qbus_config.get_device_by_id.return_value = QbusMqttDevice(
        {"serialNr": "000001"}
    )

    with (
        patch.object(
            QbusConfigCoordinator,
            "async_get_or_request_config",
            return_value=mock_qbus_config,
            autospec=True,
        ) as mock_get_config,
        patch.object(
            qbus_config_flow,
            "async_step_discovery_confirm",
            return_value={"type": FlowResultType.FORM},
        ) as mock_step_discovery,
    ):
        result = await qbus_config_flow._async_handle_device_topic(
            mqtt_discovery_info_device
        )

    assert mock_get_config.called
    assert mock_step_discovery.called
    assert result.get("type") == FlowResultType.FORM


async def test_handle_device_topic_missing_config(
    qbus_config_flow: QbusFlowHandler, mqtt_discovery_info_device: MqttServiceInfo
) -> None:
    """Test handling of device topic when config is missing."""
    with (
        patch.object(
            QbusConfigCoordinator,
            "async_get_or_request_config",
            return_value=None,
        ) as mock_get_config,
    ):
        result = await qbus_config_flow._async_handle_device_topic(
            mqtt_discovery_info_device
        )

    assert mock_get_config.called
    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "invalid_discovery_info"


async def test_handle_device_topic_device_not_found(
    qbus_config_flow: QbusFlowHandler, mqtt_discovery_info_device: MqttServiceInfo
) -> None:
    """Test handling of device topic when device is not found."""

    mock_qbus_config = MagicMock(spec=QbusDiscovery)
    mock_qbus_config.get_device_by_id.return_value = None

    with patch.object(
        QbusConfigCoordinator,
        "async_get_or_request_config",
        return_value=mock_qbus_config,
    ):
        result = await qbus_config_flow._async_handle_device_topic(
            mqtt_discovery_info_device
        )

    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "invalid_discovery_info"


async def test_step_discovery_confirm_form(
    qbus_config_flow_with_device: QbusFlowHandler,
) -> None:
    """Test mqtt confirm showing the form."""
    result = await qbus_config_flow_with_device.async_step_discovery_confirm()

    assert result.get("type") == FlowResultType.FORM


async def test_step_discovery_confirm_create_entry(
    qbus_config_flow_with_device: QbusFlowHandler,
) -> None:
    """Test mqtt confirm creating the entry."""
    user_input = {}
    result = await qbus_config_flow_with_device.async_step_discovery_confirm(user_input)

    assert result.get("type") == FlowResultType.CREATE_ENTRY
    assert result.get("data") == {
        CONF_ID: "UL1",
        CONF_SERIAL_NUMBER: "000001",
    }


async def test_step_user_not_supported(
    qbus_config_flow: QbusFlowHandler,
) -> None:
    """Test user step, which should abort."""
    result = await qbus_config_flow.async_step_user()

    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "not_supported"
