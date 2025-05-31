"""Define tests for the Airzone config flow."""

from unittest.mock import patch

from airzone_mqtt.const import AMT_ONLINE, AMT_RESPONSE
from airzone_mqtt.exceptions import AirzoneMqttError

from homeassistant.components.airzone_mqtt.const import CONF_MQTT_TOPIC, DOMAIN
from homeassistant.components.mqtt.subscription import (  # pylint: disable=hass-component-root-import
    async_prepare_subscribe_topics,
    async_subscribe_topics,
    async_unsubscribe_topics,
)
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResultType

from .util import (
    CONFIG,
    airzone_topic,
    mock_az_get_status,
    mock_cmd_req_id,
    mock_online,
)

from tests.common import MockConfigEntry, async_fire_mqtt_message
from tests.typing import MqttMockHAClient


async def test_form(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
) -> None:
    """Test that the form is served with valid input."""

    with (
        patch(
            "homeassistant.components.airzone_mqtt.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
        patch(
            "homeassistant.components.airzone_mqtt.AirzoneMqttApi.cmd_req_id",
            side_effect=mock_cmd_req_id,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {}

        calls = []

        @callback
        def mqtt_invoke(*args):
            """Record calls."""
            calls.append(args)

            async_fire_mqtt_message(
                hass=hass,
                topic=airzone_topic(AMT_ONLINE),
                payload=mock_online(),
            )

            async_fire_mqtt_message(
                hass=hass,
                topic=airzone_topic(f"{AMT_RESPONSE}/az_get_status"),
                payload=mock_az_get_status(),
            )

        sub_state = None
        sub_state = async_prepare_subscribe_topics(
            hass,
            sub_state,
            {
                "az_get_status": {
                    "topic": f"{CONFIG[CONF_MQTT_TOPIC]}/v1/invoke",
                    "msg_callback": mqtt_invoke,
                },
            },
        )
        await async_subscribe_topics(hass, sub_state)

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            CONFIG,
        )

        await hass.async_block_till_done()

        assert len(calls) == 1
        assert calls[0][0].topic == f"{CONFIG[CONF_MQTT_TOPIC]}/v1/invoke"

        async_unsubscribe_topics(hass, sub_state)

        conf_entries = hass.config_entries.async_entries(DOMAIN)
        entry = conf_entries[0]
        assert entry.state is ConfigEntryState.LOADED

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == f"Airzone MQTT {CONFIG[CONF_MQTT_TOPIC]}"
        assert result["data"][CONF_MQTT_TOPIC] == CONFIG[CONF_MQTT_TOPIC]

        assert len(mock_setup_entry.mock_calls) == 1


async def test_error_connection(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
) -> None:
    """Test connection to host error."""

    with patch(
        "homeassistant.components.airzone_mqtt.AirzoneMqttApi.update",
        side_effect=AirzoneMqttError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=CONFIG,
        )

        assert result["errors"] == {"base": "cannot_connect"}


async def test_error_mqtt(
    hass: HomeAssistant,
) -> None:
    """Test connection to host error."""

    with patch(
        "homeassistant.components.airzone_mqtt.AirzoneMqttApi.update",
        side_effect=AirzoneMqttError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=CONFIG,
        )

        assert result["errors"] == {"base": "mqtt_unavailable"}


async def test_form_duplicated_id(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
) -> None:
    """Test setting up duplicated entry."""

    config_entry = MockConfigEntry(
        data=CONFIG,
        domain=DOMAIN,
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=CONFIG,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
