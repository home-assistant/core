"""The tests for the StatsD feeder."""
import unittest
from unittest import mock

import pytest
import voluptuous as vol

import homeassistant.components.statsd as statsd
from homeassistant.const import EVENT_STATE_CHANGED, STATE_OFF, STATE_ON
import homeassistant.core as ha
from homeassistant.setup import async_setup_component, setup_component

from tests.async_mock import MagicMock, Mock, patch


@pytest.fixture
def mock_client():
    with patch("statsd.StatsClient") as mock_client:
        yield mock_client.return_value


def test_invalid_config():
    """Test configuration with defaults."""
    config = {"statsd": {"host1": "host1"}}

    with pytest.raises(vol.Invalid):
        statsd.CONFIG_SCHEMA(None)
    with pytest.raises(vol.Invalid):
        statsd.CONFIG_SCHEMA(config)


async def test_statsd_setup_full(hass, mock_client):
    """Test setup with all data."""
    config = {"statsd": {"host": "host", "port": 123, "rate": 1, "prefix": "foo"}}
    hass.bus.listen = MagicMock()
    assert await async_setup_component(hass, statsd.DOMAIN, config)

    for attr in dir(mock_client):
        print("mock_client.{} = {!r}".format(attr, getattr(mock_client, attr)))
    assert mock_client.call_count == 1
    assert mock_client.call_args == mock.call(host="host", port=123, prefix="foo")

    assert hass.bus.listen.called
    assert EVENT_STATE_CHANGED == hass.bus.listen.call_args_list[0][0][0]


async def test_statsd_setup_defaults(hass, mock_client):
    """Test setup with defaults."""
    config = {"statsd": {"host": "host"}}

    config["statsd"][statsd.CONF_PORT] = statsd.DEFAULT_PORT
    config["statsd"][statsd.CONF_PREFIX] = statsd.DEFAULT_PREFIX

    hass.bus.listen = MagicMock()
    assert await async_setup_component(hass, statsd.DOMAIN, config)

    assert mock_client.call_count == 1
    assert mock_client.call_args == mock.call(host="host", port=8125, prefix="hass")
    assert hass.bus.listen.called


async def test_event_listener_defaults(hass, mock_client):
    """Test event listener."""
    config = {"statsd": {"host": "host", "value_mapping": {"custom": 3}}}

    config["statsd"][statsd.CONF_RATE] = statsd.DEFAULT_RATE

    hass.bus.listen = MagicMock()
    await async_setup_component(hass, statsd.DOMAIN, config)
    assert hass.bus.listen.called
    handler_method = hass.bus.listen.call_args_list[0][0][1]

    valid = {"1": 1, "1.0": 1.0, "custom": 3, STATE_ON: 1, STATE_OFF: 0}
    for in_, out in valid.items():
        state = MagicMock(state=in_, attributes={"attribute key": 3.2})
        handler_method(MagicMock(data={"new_state": state}))
        mock_client.gauge.assert_has_calls(
            [mock.call(state.entity_id, out, statsd.DEFAULT_RATE)]
        )

        mock_client.gauge.reset_mock()

        assert mock_client.incr.call_count == 1
        assert mock_client.incr.call_args == mock.call(
            state.entity_id, rate=statsd.DEFAULT_RATE
        )
        mock_client.incr.reset_mock()

    for invalid in ("foo", "", object):
        handler_method(
            MagicMock(data={"new_state": ha.State("domain.test", invalid, {})})
        )
        assert not mock_client.gauge.called
        assert mock_client.incr.called


async def test_event_listener_attr_details(hass, mock_client):
    """Test event listener."""
    config = {"statsd": {"host": "host", "log_attributes": True}}

    config["statsd"][statsd.CONF_RATE] = statsd.DEFAULT_RATE

    hass.bus.listen = MagicMock()
    await async_setup_component(hass, statsd.DOMAIN, config)
    assert hass.bus.listen.called
    handler_method = hass.bus.listen.call_args_list[0][0][1]

    valid = {"1": 1, "1.0": 1.0, STATE_ON: 1, STATE_OFF: 0}
    for in_, out in valid.items():
        state = MagicMock(state=in_, attributes={"attribute key": 3.2})
        handler_method(MagicMock(data={"new_state": state}))
        mock_client.gauge.assert_has_calls(
            [
                mock.call("%s.state" % state.entity_id, out, statsd.DEFAULT_RATE),
                mock.call(
                    "%s.attribute_key" % state.entity_id, 3.2, statsd.DEFAULT_RATE
                ),
            ]
        )

        mock_client.gauge.reset_mock()

        assert mock_client.incr.call_count == 1
        assert mock_client.incr.call_args == mock.call(
            state.entity_id, rate=statsd.DEFAULT_RATE
        )
        mock_client.incr.reset_mock()

    for invalid in ("foo", "", object):
        handler_method(
            MagicMock(data={"new_state": ha.State("domain.test", invalid, {})})
        )
        assert not mock_client.gauge.called
        assert mock_client.incr.called
