"""The tests for the Datadog component."""
from unittest import mock
from unittest.mock import MagicMock, patch

import homeassistant.components.datadog as datadog
from homeassistant.const import (
    EVENT_LOGBOOK_ENTRY,
    EVENT_STATE_CHANGED,
    STATE_OFF,
    STATE_ON,
)
import homeassistant.core as ha
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import assert_setup_component


async def test_invalid_config(hass: HomeAssistant) -> None:
    """Test invalid configuration."""
    with assert_setup_component(0):
        assert not await async_setup_component(
            hass, datadog.DOMAIN, {datadog.DOMAIN: {"host1": "host1"}}
        )


async def test_datadog_setup_full(hass: HomeAssistant) -> None:
    """Test setup with all data."""
    config = {datadog.DOMAIN: {"host": "host", "port": 123, "rate": 1, "prefix": "foo"}}
    hass.bus.listen = MagicMock()

    with patch("homeassistant.components.datadog.initialize") as mock_init, patch(
        "homeassistant.components.datadog.statsd"
    ):
        assert await async_setup_component(hass, datadog.DOMAIN, config)

        assert mock_init.call_count == 1
        assert mock_init.call_args == mock.call(statsd_host="host", statsd_port=123)

    assert hass.bus.listen.called
    assert hass.bus.listen.call_args_list[0][0][0] == EVENT_LOGBOOK_ENTRY
    assert hass.bus.listen.call_args_list[1][0][0] == EVENT_STATE_CHANGED


async def test_datadog_setup_defaults(hass: HomeAssistant) -> None:
    """Test setup with defaults."""
    hass.bus.listen = mock.MagicMock()

    with patch("homeassistant.components.datadog.initialize") as mock_init, patch(
        "homeassistant.components.datadog.statsd"
    ):
        assert await async_setup_component(
            hass,
            datadog.DOMAIN,
            {
                datadog.DOMAIN: {
                    "host": "host",
                    "port": datadog.DEFAULT_PORT,
                    "prefix": datadog.DEFAULT_PREFIX,
                }
            },
        )

        assert mock_init.call_count == 1
        assert mock_init.call_args == mock.call(statsd_host="host", statsd_port=8125)
    assert hass.bus.listen.called


async def test_logbook_entry(hass: HomeAssistant) -> None:
    """Test event listener."""
    hass.bus.listen = mock.MagicMock()

    with patch("homeassistant.components.datadog.initialize"), patch(
        "homeassistant.components.datadog.statsd"
    ) as mock_statsd:
        assert await async_setup_component(
            hass,
            datadog.DOMAIN,
            {datadog.DOMAIN: {"host": "host", "rate": datadog.DEFAULT_RATE}},
        )

        assert hass.bus.listen.called
        handler_method = hass.bus.listen.call_args_list[0][0][1]

        event = {
            "domain": "automation",
            "entity_id": "sensor.foo.bar",
            "message": "foo bar biz",
            "name": "triggered something",
        }
        handler_method(mock.MagicMock(data=event))

        assert mock_statsd.event.call_count == 1
        assert mock_statsd.event.call_args == mock.call(
            title="Home Assistant",
            text="%%% \n **{}** {} \n %%%".format(event["name"], event["message"]),
            tags=["entity:sensor.foo.bar", "domain:automation"],
        )

        mock_statsd.event.reset_mock()


async def test_state_changed(hass: HomeAssistant) -> None:
    """Test event listener."""
    hass.bus.listen = mock.MagicMock()

    with patch("homeassistant.components.datadog.initialize"), patch(
        "homeassistant.components.datadog.statsd"
    ) as mock_statsd:
        assert await async_setup_component(
            hass,
            datadog.DOMAIN,
            {
                datadog.DOMAIN: {
                    "host": "host",
                    "prefix": "ha",
                    "rate": datadog.DEFAULT_RATE,
                }
            },
        )

        assert hass.bus.listen.called
        handler_method = hass.bus.listen.call_args_list[1][0][1]

        valid = {"1": 1, "1.0": 1.0, STATE_ON: 1, STATE_OFF: 0}

        attributes = {"elevation": 3.2, "temperature": 5.0, "up": True, "down": False}

        for in_, out in valid.items():
            state = mock.MagicMock(
                domain="sensor",
                entity_id="sensor.foo.bar",
                state=in_,
                attributes=attributes,
            )
            handler_method(mock.MagicMock(data={"new_state": state}))

            assert mock_statsd.gauge.call_count == 5

            for attribute, value in attributes.items():
                value = int(value) if isinstance(value, bool) else value
                mock_statsd.gauge.assert_has_calls(
                    [
                        mock.call(
                            f"ha.sensor.{attribute}",
                            value,
                            sample_rate=1,
                            tags=[f"entity:{state.entity_id}"],
                        )
                    ]
                )

            assert mock_statsd.gauge.call_args == mock.call(
                "ha.sensor",
                out,
                sample_rate=1,
                tags=[f"entity:{state.entity_id}"],
            )

            mock_statsd.gauge.reset_mock()

        for invalid in ("foo", "", object):
            handler_method(
                mock.MagicMock(data={"new_state": ha.State("domain.test", invalid, {})})
            )
            assert not mock_statsd.gauge.called
