"""Test the qingpingiot config flow."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.qingpingiot.config_flow import (
    MANUAL_ENTRY_STRING,
    QingpingConfigFlow,
)
from homeassistant.components.qingpingiot.const import DOMAIN
from homeassistant.config_entries import SOURCE_RECONFIGURE, SOURCE_USER
from homeassistant.const import CONF_MAC, CONF_MODEL, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_user_step_no_discovered_devices_goes_to_manual(
    hass: HomeAssistant,
) -> None:
    """Test user step redirects to manual when no devices discovered."""
    with patch(
        "homeassistant.components.qingpingiot.config_flow.mqtt.async_wait_for_mqtt_client",
        return_value=False,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"


async def test_manual_flow_creates_entry(hass: HomeAssistant) -> None:
    """Test manual device entry creates a config entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "My Device",
            CONF_MAC: "AA:BB:CC:DD:EE:FF",
            CONF_MODEL: "cgr1w",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "My Device"
    assert result["data"][CONF_MAC] == "AABBCCDDEEFF"
    assert result["data"][CONF_MODEL] == "cgr1w"
    assert result["data"][CONF_NAME] == "My Device"


async def test_manual_flow_invalid_mac(hass: HomeAssistant) -> None:
    """Test manual flow with invalid MAC shows error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Bad Device",
            CONF_MAC: "invalid",
            CONF_MODEL: "cgr1w",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_mac"}

    # Recover with valid input
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Good Device",
            CONF_MAC: "AABBCCDDEEFF",
            CONF_MODEL: "cgr1w",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_manual_flow_short_mac(hass: HomeAssistant) -> None:
    """Test manual flow with too short MAC."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Short MAC",
            CONF_MAC: "AABB",
            CONF_MODEL: "cgr1w",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_mac"}


async def test_manual_flow_already_configured(hass: HomeAssistant) -> None:
    """Test manual flow aborts if device already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="AABBCCDDEEFF",
        data={
            CONF_MAC: "AABBCCDDEEFF",
            CONF_MODEL: "cgr1w",
            CONF_NAME: "Existing Device",
        },
        title="Existing Device",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "New Device",
            CONF_MAC: "AABBCCDDEEFF",
            CONF_MODEL: "cgr1w",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_discovered_device_flow(
    hass: HomeAssistant,
) -> None:
    """Test flow with a discovered device via MQTT."""
    with (
        patch(
            "homeassistant.components.qingpingiot.config_flow.mqtt.async_wait_for_mqtt_client",
            return_value=True,
        ),
        patch(
            "homeassistant.components.qingpingiot.config_flow.mqtt.async_subscribe",
        ) as mock_subscribe,
    ):
        async def fake_subscribe(hass, topic, callback, qos, **kwargs):
            # Simulate a discovered device message
            from homeassistant.components.mqtt.models import ReceiveMessage

            msg = ReceiveMessage(
                topic="qingping/aa:bb:cc:dd:ee:ff/up",
                payload=b"test",
                qos=0,
                retain=False,
                subscribed_topic="qingping/#",
                timestamp=0,
            )
            callback(msg)
            return AsyncMock()

        mock_subscribe.side_effect = fake_subscribe

        with patch(
            "homeassistant.components.qingpingiot.config_flow.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_USER}
            )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # Select the discovered device
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"device": "AABBCCDDEEFF"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"

    # Confirm the device
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "My Qingping",
            CONF_MODEL: "cgr1w",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_MAC] == "AABBCCDDEEFF"


async def test_user_select_manual_from_discovered_list(
    hass: HomeAssistant,
) -> None:
    """Test selecting manual entry from discovered devices list."""
    with (
        patch(
            "homeassistant.components.qingpingiot.config_flow.mqtt.async_wait_for_mqtt_client",
            return_value=True,
        ),
        patch(
            "homeassistant.components.qingpingiot.config_flow.mqtt.async_subscribe",
        ) as mock_subscribe,
    ):
        async def fake_subscribe(hass, topic, callback, qos, **kwargs):
            from homeassistant.components.mqtt.models import ReceiveMessage

            msg = ReceiveMessage(
                topic="qingping/aa:bb:cc:dd:ee:ff/up",
                payload=b"test",
                qos=0,
                retain=False,
                subscribed_topic="qingping/#",
                timestamp=0,
            )
            callback(msg)
            return AsyncMock()

        mock_subscribe.side_effect = fake_subscribe

        with patch(
            "homeassistant.components.qingpingiot.config_flow.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_USER}
            )

    assert result["step_id"] == "user"

    # Select manual entry
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"device": MANUAL_ENTRY_STRING},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"


async def test_reconfigure_flow(
    hass: HomeAssistant,
    mqtt_mock: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the reconfigure flow updates the model."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_RECONFIGURE,
            "entry_id": mock_config_entry.entry_id,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_MODEL: "cgf2w"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"


def test_is_valid_mac() -> None:
    """Test MAC validation."""
    assert QingpingConfigFlow._is_valid_mac("AABBCCDDEEFF") is True
    assert QingpingConfigFlow._is_valid_mac("aabbccddeeff") is True
    assert QingpingConfigFlow._is_valid_mac("1234567890AB") is True
    assert QingpingConfigFlow._is_valid_mac("invalid") is False
    assert QingpingConfigFlow._is_valid_mac("AABBCC") is False
    assert QingpingConfigFlow._is_valid_mac("") is False
    assert QingpingConfigFlow._is_valid_mac("AABBCCDDEEFFGG") is False
    assert QingpingConfigFlow._is_valid_mac("GGHHIIJJKKLL") is False
