"""The tests for the Datadog component."""
from unittest import mock
from unittest.mock import patch

import homeassistant.components.datadog as datadog
from homeassistant.const import (
    EVENT_LOGBOOK_ENTRY,
    STATE_OFF,
    STATE_ON,
)
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

    with patch("homeassistant.components.datadog.initialize") as mock_init, patch(
        "homeassistant.components.datadog.statsd"
    ):
        assert await async_setup_component(hass, datadog.DOMAIN, config)

        assert mock_init.call_count == 1
        assert mock_init.call_args == mock.call(statsd_host="host", statsd_port=123)


async def test_datadog_setup_defaults(hass: HomeAssistant) -> None:
    """Test setup with defaults."""
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


async def test_logbook_entry(hass: HomeAssistant) -> None:
    """Test event listener."""
    with patch("homeassistant.components.datadog.initialize"), patch(
        "homeassistant.components.datadog.statsd"
    ) as mock_statsd:
        assert await async_setup_component(
            hass,
            datadog.DOMAIN,
            {datadog.DOMAIN: {"host": "host", "rate": datadog.DEFAULT_RATE}},
        )

        event = {
            "domain": "automation",
            "entity_id": "sensor.foo.bar",
            "message": "foo bar biz",
            "name": "triggered something",
        }
        hass.bus.async_fire(EVENT_LOGBOOK_ENTRY, event)
        await hass.async_block_till_done()

        assert mock_statsd.event.call_count == 1
        assert mock_statsd.event.call_args == mock.call(
            title="Home Assistant",
            text="%%% \n **{}** {} \n %%%".format(event["name"], event["message"]),
            tags=["entity:sensor.foo.bar", "domain:automation"],
        )

        mock_statsd.event.reset_mock()


async def test_state_changed(hass: HomeAssistant) -> None:
    """Test event listener."""
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

        valid = {"1": 1, "1.0": 1.0, STATE_ON: 1, STATE_OFF: 0}

        attributes = {"elevation": 3.2, "temperature": 5.0, "up": True, "down": False}

        for in_, out in valid.items():
            state = mock.MagicMock(
                domain="sensor",
                entity_id="sensor.foobar",
                state=in_,
                attributes=attributes,
            )
            hass.states.async_set(state.entity_id, state.state, state.attributes)
            await hass.async_block_till_done()
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
            hass.states.async_set("domain.test", invalid, {})
            await hass.async_block_till_done()
            assert not mock_statsd.gauge.called
