"""The tests for the Datadog component."""

from unittest import mock
from unittest.mock import patch

from homeassistant.components import datadog
from homeassistant.components.datadog.config_flow import validate_datadog_connection
from homeassistant.const import EVENT_LOGBOOK_ENTRY, STATE_OFF, STATE_ON, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .common import MOCK_CONFIG, create_mock_state

from tests.common import EVENT_STATE_CHANGED, MockConfigEntry, assert_setup_component


async def test_invalid_config(hass: HomeAssistant) -> None:
    """Test invalid configuration."""
    with assert_setup_component(0):
        assert not await async_setup_component(
            hass, datadog.DOMAIN, {datadog.DOMAIN: {"host1": "host1"}}
        )


async def test_datadog_setup_full(hass: HomeAssistant) -> None:
    """Test setup with all data."""
    config = {datadog.DOMAIN: {"host": "host", "port": 123, "rate": 1, "prefix": "foo"}}

    with (
        patch(
            "homeassistant.components.datadog.config_flow.DogStatsd"
        ) as mock_dogstatsd,
    ):
        assert await async_setup_component(hass, datadog.DOMAIN, config)

        assert mock_dogstatsd.call_count == 1
        assert mock_dogstatsd.call_args == mock.call("host", 123, "foo")


async def test_datadog_setup_defaults(hass: HomeAssistant) -> None:
    """Test setup with defaults."""
    with (
        patch(
            "homeassistant.components.datadog.config_flow.DogStatsd"
        ) as mock_dogstatsd,
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

        assert mock_dogstatsd.call_count == 1
        assert mock_dogstatsd.call_args == mock.call("host", 8125, "hass")


async def test_logbook_entry(hass: HomeAssistant) -> None:
    """Test event listener."""
    with (
        patch("homeassistant.components.datadog.DogStatsd") as mock_statsd_class,
        patch(
            "homeassistant.components.datadog.config_flow.DogStatsd", mock_statsd_class
        ),
    ):
        mock_statsd = mock_statsd_class.return_value

        assert await async_setup_component(
            hass,
            datadog.DOMAIN,
            {
                datadog.DOMAIN: {
                    "host": "host",
                    "port": datadog.DEFAULT_PORT,
                    "rate": datadog.DEFAULT_RATE,
                    "prefix": datadog.DEFAULT_PREFIX,
                }
            },
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
            message=f"%%% \n **{event['name']}** {event['message']} \n %%%",
            tags=["entity:sensor.foo.bar", "domain:automation"],
        )


async def test_state_changed(hass: HomeAssistant) -> None:
    """Test event listener."""
    with (
        patch("homeassistant.components.datadog.DogStatsd") as mock_statsd_class,
        patch(
            "homeassistant.components.datadog.config_flow.DogStatsd", mock_statsd_class
        ),
    ):
        mock_statsd = mock_statsd_class.return_value

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
            state = create_mock_state("sensor.foobar", in_, attributes)
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


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test unloading the config entry cleans up properly."""
    client = mock.MagicMock()

    with (
        patch("homeassistant.components.datadog.DogStatsd", return_value=client),
        patch("homeassistant.components.datadog.initialize"),
    ):
        entry = MockConfigEntry(
            domain=datadog.DOMAIN,
            options=MOCK_CONFIG,
        )
        entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

    client.flush.assert_called_once()
    client.close_socket.assert_called_once()


async def test_validate_connection_success(hass: HomeAssistant) -> None:
    """Test validate_datadog_connection succeeds."""
    with (
        patch(
            "homeassistant.components.datadog.config_flow.DogStatsd.increment"
        ) as mock_increment,
    ):
        result = await validate_datadog_connection(hass, MOCK_CONFIG)
        assert result is True
        mock_increment.assert_called_once_with("connection_test")


async def test_validate_connection_oserror(hass: HomeAssistant) -> None:
    """Test validate_datadog_connection fails with OSError."""
    with (
        patch(
            "homeassistant.components.datadog.config_flow.DogStatsd.increment",
            side_effect=OSError,
        ),
    ):
        result = await validate_datadog_connection(hass, MOCK_CONFIG)
        assert result is False


async def test_validate_connection_valueerror(hass: HomeAssistant) -> None:
    """Test validate_datadog_connection fails with ValueError."""
    with (
        patch(
            "homeassistant.components.datadog.config_flow.DogStatsd.increment",
            side_effect=ValueError,
        ),
    ):
        result = await validate_datadog_connection(hass, MOCK_CONFIG)
        assert result is False


async def test_state_changed_skips_unknown(hass: HomeAssistant) -> None:
    """Test state_changed_listener skips None and unknown states."""
    with (
        patch(
            "homeassistant.components.datadog.config_flow.DogStatsd"
        ) as mock_dogstatsd,
    ):
        assert await async_setup_component(
            hass,
            datadog.DOMAIN,
            {
                datadog.DOMAIN: {
                    "host": "host",
                    "prefix": "ha",
                    "rate": 1,
                }
            },
        )

        # Test None state
        hass.bus.async_fire(EVENT_STATE_CHANGED, {"new_state": None})
        await hass.async_block_till_done()
        assert not mock_dogstatsd.gauge.called

        # Test STATE_UNKNOWN
        unknown_state = mock.MagicMock()
        unknown_state.state = STATE_UNKNOWN
        hass.bus.async_fire(EVENT_STATE_CHANGED, {"new_state": unknown_state})
        await hass.async_block_till_done()
        assert not mock_dogstatsd.gauge.called
