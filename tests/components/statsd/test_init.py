"""The tests for the StatsD feeder."""

from unittest import mock
from unittest.mock import patch

import pytest
import voluptuous as vol

from homeassistant.components import statsd
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


@pytest.fixture
def mock_client():
    """Pytest fixture for statsd library."""
    with patch("statsd.StatsClient") as mock_client:
        yield mock_client.return_value


def test_invalid_config() -> None:
    """Test configuration with defaults."""
    config = {"statsd": {"host1": "host1"}}

    with pytest.raises(vol.Invalid):
        statsd.CONFIG_SCHEMA(None)
    with pytest.raises(vol.Invalid):
        statsd.CONFIG_SCHEMA(config)


async def test_statsd_setup_full(hass: HomeAssistant) -> None:
    """Test setup with all data."""
    config = {"statsd": {"host": "host", "port": 123, "rate": 1, "prefix": "foo"}}
    with patch("statsd.StatsClient") as mock_init:
        assert await async_setup_component(hass, statsd.DOMAIN, config)

        assert mock_init.call_count == 1
        assert mock_init.call_args == mock.call(host="host", port=123, prefix="foo")

        hass.states.async_set("domain.test", "on")
        await hass.async_block_till_done()
        assert len(mock_init.mock_calls) == 3


async def test_statsd_setup_defaults(hass: HomeAssistant) -> None:
    """Test setup with defaults."""
    config = {"statsd": {"host": "host"}}

    config["statsd"][statsd.CONF_PORT] = statsd.DEFAULT_PORT
    config["statsd"][statsd.CONF_PREFIX] = statsd.DEFAULT_PREFIX

    with patch("statsd.StatsClient") as mock_init:
        assert await async_setup_component(hass, statsd.DOMAIN, config)

        assert mock_init.call_count == 1
        assert mock_init.call_args == mock.call(host="host", port=8125, prefix="hass")
        hass.states.async_set("domain.test", "on")
        await hass.async_block_till_done()
        assert len(mock_init.mock_calls) == 3


async def test_event_listener_defaults(hass: HomeAssistant, mock_client) -> None:
    """Test event listener."""
    config = {"statsd": {"host": "host", "value_mapping": {"custom": 3}}}

    config["statsd"][statsd.CONF_RATE] = statsd.DEFAULT_RATE

    await async_setup_component(hass, statsd.DOMAIN, config)

    valid = {"1": 1, "1.0": 1.0, "custom": 3, STATE_ON: 1, STATE_OFF: 0}
    for in_, out in valid.items():
        hass.states.async_set("domain.test", in_, {"attribute key": 3.2})
        await hass.async_block_till_done()
        mock_client.gauge.assert_has_calls(
            [mock.call("domain.test", out, statsd.DEFAULT_RATE)]
        )

        mock_client.gauge.reset_mock()

        assert mock_client.incr.call_count == 1
        assert mock_client.incr.call_args == mock.call(
            "domain.test", rate=statsd.DEFAULT_RATE
        )
        mock_client.incr.reset_mock()

    for invalid in ("foo", "", object):
        hass.states.async_set("domain.test", invalid, {})
        await hass.async_block_till_done()
        assert not mock_client.gauge.called
        assert mock_client.incr.called


async def test_event_listener_attr_details(hass: HomeAssistant, mock_client) -> None:
    """Test event listener."""
    config = {"statsd": {"host": "host", "log_attributes": True}}

    config["statsd"][statsd.CONF_RATE] = statsd.DEFAULT_RATE

    await async_setup_component(hass, statsd.DOMAIN, config)

    valid = {"1": 1, "1.0": 1.0, STATE_ON: 1, STATE_OFF: 0}
    for in_, out in valid.items():
        hass.states.async_set("domain.test", in_, {"attribute key": 3.2})
        await hass.async_block_till_done()
        mock_client.gauge.assert_has_calls(
            [
                mock.call("domain.test.state", out, statsd.DEFAULT_RATE),
                mock.call("domain.test.attribute_key", 3.2, statsd.DEFAULT_RATE),
            ]
        )

        mock_client.gauge.reset_mock()

        assert mock_client.incr.call_count == 1
        assert mock_client.incr.call_args == mock.call(
            "domain.test", rate=statsd.DEFAULT_RATE
        )
        mock_client.incr.reset_mock()

    for invalid in ("foo", "", object):
        hass.states.async_set("domain.test", invalid, {})
        await hass.async_block_till_done()
        assert not mock_client.gauge.called
        assert mock_client.incr.called
