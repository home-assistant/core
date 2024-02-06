"""Test the Fully Kiosk Browser config flow."""

from unittest.mock import AsyncMock, MagicMock, Mock

from aiohttp.client_exceptions import ClientConnectorError
from fullykiosk import FullyKioskError
import pytest

from homeassistant.components.dhcp import DhcpServiceInfo
from homeassistant.components.fully_kiosk.const import DOMAIN
from homeassistant.config_entries import SOURCE_DHCP, SOURCE_MQTT, SOURCE_USER
from homeassistant.const import (
    CONF_HOST,
    CONF_MAC,
    CONF_PASSWORD,
    CONF_SSL,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.mqtt import MqttServiceInfo

from tests.common import MockConfigEntry, load_fixture


async def test_user_flow(
    hass: HomeAssistant,
    mock_fully_kiosk_config_flow: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test the full user initiated config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "1.1.1.1",
            CONF_PASSWORD: "test-password",
            CONF_SSL: False,
            CONF_VERIFY_SSL: False,
        },
    )

    assert result2.get("type") == FlowResultType.CREATE_ENTRY
    assert result2.get("title") == "Test device"
    assert result2.get("data") == {
        CONF_HOST: "1.1.1.1",
        CONF_PASSWORD: "test-password",
        CONF_MAC: "aa:bb:cc:dd:ee:ff",
        CONF_SSL: False,
        CONF_VERIFY_SSL: False,
    }
    assert "result" in result2
    assert result2["result"].unique_id == "12345"

    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_fully_kiosk_config_flow.getDeviceInfo.mock_calls) == 1


@pytest.mark.parametrize(
    ("side_effect", "reason"),
    [
        (FullyKioskError("error", "status"), "cannot_connect"),
        (ClientConnectorError(None, Mock()), "cannot_connect"),
        (TimeoutError, "cannot_connect"),
        (RuntimeError, "unknown"),
    ],
)
async def test_errors(
    hass: HomeAssistant,
    mock_fully_kiosk_config_flow: MagicMock,
    mock_setup_entry: AsyncMock,
    side_effect: Exception,
    reason: str,
) -> None:
    """Test errors raised during flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    flow_id = result["flow_id"]

    mock_fully_kiosk_config_flow.getDeviceInfo.side_effect = side_effect
    result2 = await hass.config_entries.flow.async_configure(
        flow_id,
        user_input={
            CONF_HOST: "1.1.1.1",
            CONF_PASSWORD: "test-password",
            CONF_SSL: False,
            CONF_VERIFY_SSL: False,
        },
    )

    assert result2.get("type") == FlowResultType.FORM
    assert result2.get("step_id") == "user"
    assert result2.get("errors") == {"base": reason}

    assert len(mock_fully_kiosk_config_flow.getDeviceInfo.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 0

    mock_fully_kiosk_config_flow.getDeviceInfo.side_effect = None
    result3 = await hass.config_entries.flow.async_configure(
        flow_id,
        user_input={
            CONF_HOST: "1.1.1.1",
            CONF_PASSWORD: "test-password",
            CONF_SSL: True,
            CONF_VERIFY_SSL: False,
        },
    )

    assert result3.get("type") == FlowResultType.CREATE_ENTRY
    assert result3.get("title") == "Test device"
    assert result3.get("data") == {
        CONF_HOST: "1.1.1.1",
        CONF_PASSWORD: "test-password",
        CONF_MAC: "aa:bb:cc:dd:ee:ff",
        CONF_SSL: True,
        CONF_VERIFY_SSL: False,
    }
    assert "result" in result3
    assert result3["result"].unique_id == "12345"

    assert len(mock_fully_kiosk_config_flow.getDeviceInfo.mock_calls) == 2
    assert len(mock_setup_entry.mock_calls) == 1


async def test_duplicate_updates_existing_entry(
    hass: HomeAssistant,
    mock_fully_kiosk_config_flow: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test adding existing device updates existing entry."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "1.1.1.1",
            CONF_PASSWORD: "test-password",
            CONF_SSL: True,
            CONF_VERIFY_SSL: True,
        },
    )

    assert result2.get("type") == FlowResultType.ABORT
    assert result2.get("reason") == "already_configured"
    assert mock_config_entry.data == {
        CONF_HOST: "1.1.1.1",
        CONF_PASSWORD: "test-password",
        CONF_MAC: "aa:bb:cc:dd:ee:ff",
        CONF_SSL: True,
        CONF_VERIFY_SSL: True,
    }

    assert len(mock_fully_kiosk_config_flow.getDeviceInfo.mock_calls) == 1


async def test_dhcp_discovery_updates_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test DHCP discovery updates config entries."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DhcpServiceInfo(
            hostname="tablet",
            ip="127.0.0.2",
            macaddress="aa:bb:cc:dd:ee:ff",
        ),
    )

    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "already_configured"
    assert mock_config_entry.data == {
        CONF_HOST: "127.0.0.2",
        CONF_PASSWORD: "mocked-password",
        CONF_MAC: "aa:bb:cc:dd:ee:ff",
        CONF_SSL: False,
        CONF_VERIFY_SSL: False,
    }


async def test_dhcp_unknown_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unknown DHCP discovery aborts flow."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DhcpServiceInfo(
            hostname="tablet",
            ip="127.0.0.2",
            macaddress="aa:bb:cc:dd:ee:00",
        ),
    )

    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "unknown"


async def test_mqtt_discovery_flow(
    hass: HomeAssistant,
    mock_fully_kiosk_config_flow: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test MQTT discovery configuration flow."""
    payload = load_fixture("mqtt-discovery-deviceinfo.json", DOMAIN)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_MQTT},
        data=MqttServiceInfo(
            topic="fully/deviceInfo/e1c9bb1-df31b345",
            payload=payload,
            qos=0,
            retain=False,
            subscribed_topic="fully/deviceInfo/+",
            timestamp=None,
        ),
    )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "discovery_confirm"

    confirmResult = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_PASSWORD: "test-password",
            CONF_SSL: False,
            CONF_VERIFY_SSL: False,
        },
    )

    assert confirmResult
    assert confirmResult.get("type") == FlowResultType.CREATE_ENTRY
    assert confirmResult.get("title") == "Test device"
    assert confirmResult.get("data") == {
        CONF_HOST: "192.168.1.234",
        CONF_PASSWORD: "test-password",
        CONF_MAC: "aa:bb:cc:dd:ee:ff",
        CONF_SSL: False,
        CONF_VERIFY_SSL: False,
    }
    assert "result" in confirmResult
    assert confirmResult["result"].unique_id == "12345"

    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_fully_kiosk_config_flow.getDeviceInfo.mock_calls) == 1
