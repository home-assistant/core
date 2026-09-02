"""Test the qingping_mqtt config flow."""

from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.components.qingping_mqtt.const import DOMAIN, MQTT_TOPIC_PREFIX
from homeassistant.const import CONF_MAC, CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult, FlowResultType

from . import MQTT_MAC, MQTT_TLV_PAYLOAD

from tests.common import MockConfigEntry, async_fire_mqtt_message
from tests.typing import MqttMockHAClient


async def _async_start_user_flow(hass: HomeAssistant) -> FlowResult:
    """Start the user flow while a device is publishing on MQTT."""

    async def _fire_device_message(_: float) -> None:
        async_fire_mqtt_message(
            hass, f"{MQTT_TOPIC_PREFIX}/{MQTT_MAC.lower()}/up", MQTT_TLV_PAYLOAD
        )

    with (
        patch(
            "homeassistant.components.qingping_mqtt.config_flow.MQTT_DISCOVERY_TIMEOUT",
            0,
        ),
        patch(
            "homeassistant.components.qingping_mqtt.config_flow.asyncio.sleep",
            _fire_device_message,
        ),
    ):
        return await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )


def _mac_options(result: FlowResult) -> list[str]:
    """Return the MAC addresses offered by the user form."""
    mac_selector = next(
        value
        for key, value in result["data_schema"].schema.items()
        if key.schema == CONF_MAC
    )
    return [option["value"] for option in mac_selector.config["options"]]


async def test_async_step_user_mqtt_not_configured(hass: HomeAssistant) -> None:
    """Test the flow aborts when the MQTT integration is not set up."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "mqtt_not_configured"


async def test_async_step_user_discovered(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test a device publishing on MQTT is offered and creates an entry."""
    result = await _async_start_user_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert MQTT_MAC in _mac_options(result)

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_MAC: MQTT_MAC, CONF_MODEL: "cgr1w"},
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == f"Qingping Indoor Environment Monitor ({MQTT_MAC})"
    assert result2["data"] == {CONF_MAC: MQTT_MAC, CONF_MODEL: "cgr1w"}
    assert result2["result"].unique_id == MQTT_MAC
    assert len(mock_setup_entry.mock_calls) == 1


async def test_async_step_user_manual_mac_without_discovery(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test manual MAC entry when no device is publishing."""
    with patch(
        "homeassistant.components.qingping_mqtt.config_flow.MQTT_DISCOVERY_TIMEOUT",
        0,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert _mac_options(result) == []

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_MAC: MQTT_MAC, CONF_MODEL: "cgr1w"},
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["data"] == {CONF_MAC: MQTT_MAC, CONF_MODEL: "cgr1w"}


async def test_async_step_user_invalid_mac(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test manual MAC entry rejects an invalid address."""
    result = await _async_start_user_flow(hass)

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_MAC: "not-a-mac", CONF_MODEL: "cgr1w"},
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {CONF_MAC: "invalid_mac"}
    assert MQTT_MAC in _mac_options(result2)

    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        user_input={CONF_MAC: "58:2d:34:12:a4:c2", CONF_MODEL: "cgr1w"},
    )
    await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["data"][CONF_MAC] == MQTT_MAC


async def test_async_step_user_already_configured(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
) -> None:
    """Test a device that is already set up is not offered again."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MQTT_MAC,
        data={CONF_MAC: MQTT_MAC, CONF_MODEL: "cgr1w"},
    )
    entry.add_to_hass(hass)

    result = await _async_start_user_flow(hass)
    assert MQTT_MAC not in _mac_options(result)

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_MAC: MQTT_MAC, CONF_MODEL: "cgr1w"},
    )
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"
