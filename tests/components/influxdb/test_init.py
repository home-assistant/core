"""The tests for the InfluxDB component."""
import datetime
import unittest
from unittest import mock

import homeassistant.components.influxdb as influxdb
from homeassistant.const import (
    EVENT_STATE_CHANGED,
    STATE_OFF,
    STATE_ON,
    STATE_STANDBY,
    UNIT_PERCENTAGE,
)
from homeassistant.setup import setup_component

from tests.common import get_test_home_assistant


@mock.patch("homeassistant.components.influxdb.InfluxDBClient")
@mock.patch(
    "homeassistant.components.influxdb.InfluxThread.batch_timeout",
    mock.Mock(return_value=0),
)
class TestInfluxDB(unittest.TestCase):
    """Test the InfluxDB component."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.handler_method = None
        self.hass.bus.listen = mock.Mock()

    def tearDown(self):
        """Clear data."""
        self.hass.stop()

    def test_setup_config_full(self, mock_client):
        """Test the setup with full configuration."""
        config = {
            "influxdb": {
                "host": "host",
                "port": 123,
                "database": "db",
                "username": "user",
                "password": "password",
                "max_retries": 4,
                "ssl": "False",
                "verify_ssl": "False",
            }
        }
        assert setup_component(self.hass, influxdb.DOMAIN, config)
        assert self.hass.bus.listen.called
        assert EVENT_STATE_CHANGED == self.hass.bus.listen.call_args_list[0][0][0]
        assert mock_client.return_value.write_points.call_count == 1

    def test_setup_config_defaults(self, mock_client):
        """Test the setup with default configuration."""
        config = {"influxdb": {"host": "host", "username": "user", "password": "pass"}}
        assert setup_component(self.hass, influxdb.DOMAIN, config)
        assert self.hass.bus.listen.called
        assert EVENT_STATE_CHANGED == self.hass.bus.listen.call_args_list[0][0][0]

    def test_setup_minimal_config(self, mock_client):
        """Test the setup with minimal configuration."""
        config = {"influxdb": {}}

        assert setup_component(self.hass, influxdb.DOMAIN, config)

    def test_setup_missing_password(self, mock_client):
        """Test the setup with existing username and missing password."""
        config = {"influxdb": {"username": "user"}}

        assert not setup_component(self.hass, influxdb.DOMAIN, config)

    def _setup(self, mock_client, **kwargs):
        """Set up the client."""
        config = {
            "influxdb": {
                "host": "host",
                "username": "user",
                "password": "pass",
                "exclude": {
                    "entities": ["fake.blacklisted"],
                    "domains": ["another_fake"],
                },
            }
        }
        config["influxdb"].update(kwargs)
        assert setup_component(self.hass, influxdb.DOMAIN, config)
        self.handler_method = self.hass.bus.listen.call_args_list[0][0][1]
        mock_client.return_value.write_points.reset_mock()

    def test_event_listener(self, mock_client):
        """Test the event listener."""
        self._setup(mock_client)

        # map of HA State to valid influxdb [state, value] fields
        valid = {
            "1": [None, 1],
            "1.0": [None, 1.0],
            STATE_ON: [STATE_ON, 1],
            STATE_OFF: [STATE_OFF, 0],
            STATE_STANDBY: [STATE_STANDBY, None],
            "foo": ["foo", None],
        }
        for in_, out in valid.items():
            attrs = {
                "unit_of_measurement": "foobars",
                "longitude": "1.1",
                "latitude": "2.2",
                "battery_level": f"99{UNIT_PERCENTAGE}",
                "temperature": "20c",
                "last_seen": "Last seen 23 minutes ago",
                "updated_at": datetime.datetime(2017, 1, 1, 0, 0),
                "multi_periods": "0.120.240.2023873",
            }
            state = mock.MagicMock(
                state=in_,
                domain="fake",
                entity_id="fake.entity-id",
                object_id="entity",
                attributes=attrs,
            )
            event = mock.MagicMock(data={"new_state": state}, time_fired=12345)
            body = [
                {
                    "measurement": "foobars",
                    "tags": {"domain": "fake", "entity_id": "entity"},
                    "time": 12345,
                    "fields": {
                        "longitude": 1.1,
                        "latitude": 2.2,
                        "battery_level_str": f"99{UNIT_PERCENTAGE}",
                        "battery_level": 99.0,
                        "temperature_str": "20c",
                        "temperature": 20.0,
                        "last_seen_str": "Last seen 23 minutes ago",
                        "last_seen": 23.0,
                        "updated_at_str": "2017-01-01 00:00:00",
                        "updated_at": 20170101000000,
                        "multi_periods_str": "0.120.240.2023873",
                    },
                }
            ]
            if out[0] is not None:
                body[0]["fields"]["state"] = out[0]
            if out[1] is not None:
                body[0]["fields"]["value"] = out[1]

            self.handler_method(event)
            self.hass.data[influxdb.DOMAIN].block_till_done()

            assert mock_client.return_value.write_points.call_count == 1
            assert mock_client.return_value.write_points.call_args == mock.call(body)
            mock_client.return_value.write_points.reset_mock()

    def test_event_listener_no_units(self, mock_client):
        """Test the event listener for missing units."""
        self._setup(mock_client)

        for unit in (None, ""):
            if unit:
                attrs = {"unit_of_measurement": unit}
            else:
                attrs = {}
            state = mock.MagicMock(
                state=1,
                domain="fake",
                entity_id="fake.entity-id",
                object_id="entity",
                attributes=attrs,
            )
            event = mock.MagicMock(data={"new_state": state}, time_fired=12345)
            body = [
                {
                    "measurement": "fake.entity-id",
                    "tags": {"domain": "fake", "entity_id": "entity"},
                    "time": 12345,
                    "fields": {"value": 1},
                }
            ]
            self.handler_method(event)
            self.hass.data[influxdb.DOMAIN].block_till_done()
            assert mock_client.return_value.write_points.call_count == 1
            assert mock_client.return_value.write_points.call_args == mock.call(body)
            mock_client.return_value.write_points.reset_mock()

    def test_event_listener_inf(self, mock_client):
        """Test the event listener for missing units."""
        self._setup(mock_client)

        attrs = {"bignumstring": "9" * 999, "nonumstring": "nan"}
        state = mock.MagicMock(
            state=8,
            domain="fake",
            entity_id="fake.entity-id",
            object_id="entity",
            attributes=attrs,
        )
        event = mock.MagicMock(data={"new_state": state}, time_fired=12345)
        body = [
            {
                "measurement": "fake.entity-id",
                "tags": {"domain": "fake", "entity_id": "entity"},
                "time": 12345,
                "fields": {"value": 8},
            }
        ]
        self.handler_method(event)
        self.hass.data[influxdb.DOMAIN].block_till_done()
        assert mock_client.return_value.write_points.call_count == 1
        assert mock_client.return_value.write_points.call_args == mock.call(body)
        mock_client.return_value.write_points.reset_mock()

    def test_event_listener_states(self, mock_client):
        """Test the event listener against ignored states."""
        self._setup(mock_client)

        for state_state in (1, "unknown", "", "unavailable"):
            state = mock.MagicMock(
                state=state_state,
                domain="fake",
                entity_id="fake.entity-id",
                object_id="entity",
                attributes={},
            )
            event = mock.MagicMock(data={"new_state": state}, time_fired=12345)
            body = [
                {
                    "measurement": "fake.entity-id",
                    "tags": {"domain": "fake", "entity_id": "entity"},
                    "time": 12345,
                    "fields": {"value": 1},
                }
            ]
            self.handler_method(event)
            self.hass.data[influxdb.DOMAIN].block_till_done()
            if state_state == 1:
                assert mock_client.return_value.write_points.call_count == 1
                assert mock_client.return_value.write_points.call_args == mock.call(
                    body
                )
            else:
                assert not mock_client.return_value.write_points.called
            mock_client.return_value.write_points.reset_mock()

    def test_event_listener_blacklist(self, mock_client):
        """Test the event listener against a blacklist."""
        self._setup(mock_client)

        for entity_id in ("ok", "blacklisted"):
            state = mock.MagicMock(
                state=1,
                domain="fake",
                entity_id="fake.{}".format(entity_id),
                object_id=entity_id,
                attributes={},
            )
            event = mock.MagicMock(data={"new_state": state}, time_fired=12345)
            body = [
                {
                    "measurement": "fake.{}".format(entity_id),
                    "tags": {"domain": "fake", "entity_id": entity_id},
                    "time": 12345,
                    "fields": {"value": 1},
                }
            ]
            self.handler_method(event)
            self.hass.data[influxdb.DOMAIN].block_till_done()
            if entity_id == "ok":
                assert mock_client.return_value.write_points.call_count == 1
                assert mock_client.return_value.write_points.call_args == mock.call(
                    body
                )
            else:
                assert not mock_client.return_value.write_points.called
            mock_client.return_value.write_points.reset_mock()

    def test_event_listener_blacklist_domain(self, mock_client):
        """Test the event listener against a blacklist."""
        self._setup(mock_client)

        for domain in ("ok", "another_fake"):
            state = mock.MagicMock(
                state=1,
                domain=domain,
                entity_id="{}.something".format(domain),
                object_id="something",
                attributes={},
            )
            event = mock.MagicMock(data={"new_state": state}, time_fired=12345)
            body = [
                {
                    "measurement": "{}.something".format(domain),
                    "tags": {"domain": domain, "entity_id": "something"},
                    "time": 12345,
                    "fields": {"value": 1},
                }
            ]
            self.handler_method(event)
            self.hass.data[influxdb.DOMAIN].block_till_done()
            if domain == "ok":
                assert mock_client.return_value.write_points.call_count == 1
                assert mock_client.return_value.write_points.call_args == mock.call(
                    body
                )
            else:
                assert not mock_client.return_value.write_points.called
            mock_client.return_value.write_points.reset_mock()

    def test_event_listener_whitelist(self, mock_client):
        """Test the event listener against a whitelist."""
        config = {
            "influxdb": {
                "host": "host",
                "username": "user",
                "password": "pass",
                "include": {"entities": ["fake.included"]},
            }
        }
        assert setup_component(self.hass, influxdb.DOMAIN, config)
        self.handler_method = self.hass.bus.listen.call_args_list[0][0][1]
        mock_client.return_value.write_points.reset_mock()

        for entity_id in ("included", "default"):
            state = mock.MagicMock(
                state=1,
                domain="fake",
                entity_id="fake.{}".format(entity_id),
                object_id=entity_id,
                attributes={},
            )
            event = mock.MagicMock(data={"new_state": state}, time_fired=12345)
            body = [
                {
                    "measurement": "fake.{}".format(entity_id),
                    "tags": {"domain": "fake", "entity_id": entity_id},
                    "time": 12345,
                    "fields": {"value": 1},
                }
            ]
            self.handler_method(event)
            self.hass.data[influxdb.DOMAIN].block_till_done()
            if entity_id == "included":
                assert mock_client.return_value.write_points.call_count == 1
                assert mock_client.return_value.write_points.call_args == mock.call(
                    body
                )
            else:
                assert not mock_client.return_value.write_points.called
            mock_client.return_value.write_points.reset_mock()

    def test_event_listener_whitelist_domain(self, mock_client):
        """Test the event listener against a whitelist."""
        config = {
            "influxdb": {
                "host": "host",
                "username": "user",
                "password": "pass",
                "include": {"domains": ["fake"]},
            }
        }
        assert setup_component(self.hass, influxdb.DOMAIN, config)
        self.handler_method = self.hass.bus.listen.call_args_list[0][0][1]
        mock_client.return_value.write_points.reset_mock()

        for domain in ("fake", "another_fake"):
            state = mock.MagicMock(
                state=1,
                domain=domain,
                entity_id="{}.something".format(domain),
                object_id="something",
                attributes={},
            )
            event = mock.MagicMock(data={"new_state": state}, time_fired=12345)
            body = [
                {
                    "measurement": "{}.something".format(domain),
                    "tags": {"domain": domain, "entity_id": "something"},
                    "time": 12345,
                    "fields": {"value": 1},
                }
            ]
            self.handler_method(event)
            self.hass.data[influxdb.DOMAIN].block_till_done()
            if domain == "fake":
                assert mock_client.return_value.write_points.call_count == 1
                assert mock_client.return_value.write_points.call_args == mock.call(
                    body
                )
            else:
                assert not mock_client.return_value.write_points.called
            mock_client.return_value.write_points.reset_mock()

    def test_event_listener_whitelist_domain_and_entities(self, mock_client):
        """Test the event listener against a whitelist."""
        config = {
            "influxdb": {
                "host": "host",
                "username": "user",
                "password": "pass",
                "include": {"domains": ["fake"], "entities": ["other.one"]},
            }
        }
        assert setup_component(self.hass, influxdb.DOMAIN, config)
        self.handler_method = self.hass.bus.listen.call_args_list[0][0][1]
        mock_client.return_value.write_points.reset_mock()

        for domain in ("fake", "another_fake"):
            state = mock.MagicMock(
                state=1,
                domain=domain,
                entity_id="{}.something".format(domain),
                object_id="something",
                attributes={},
            )
            event = mock.MagicMock(data={"new_state": state}, time_fired=12345)
            body = [
                {
                    "measurement": "{}.something".format(domain),
                    "tags": {"domain": domain, "entity_id": "something"},
                    "time": 12345,
                    "fields": {"value": 1},
                }
            ]
            self.handler_method(event)
            self.hass.data[influxdb.DOMAIN].block_till_done()
            if domain == "fake":
                assert mock_client.return_value.write_points.call_count == 1
                assert mock_client.return_value.write_points.call_args == mock.call(
                    body
                )
            else:
                assert not mock_client.return_value.write_points.called
            mock_client.return_value.write_points.reset_mock()

        for entity_id in ("one", "two"):
            state = mock.MagicMock(
                state=1,
                domain="other",
                entity_id="other.{}".format(entity_id),
                object_id=entity_id,
                attributes={},
            )
            event = mock.MagicMock(data={"new_state": state}, time_fired=12345)
            body = [
                {
                    "measurement": "other.{}".format(entity_id),
                    "tags": {"domain": "other", "entity_id": entity_id},
                    "time": 12345,
                    "fields": {"value": 1},
                }
            ]
            self.handler_method(event)
            self.hass.data[influxdb.DOMAIN].block_till_done()
            if entity_id == "one":
                assert mock_client.return_value.write_points.call_count == 1
                assert mock_client.return_value.write_points.call_args == mock.call(
                    body
                )
            else:
                assert not mock_client.return_value.write_points.called
            mock_client.return_value.write_points.reset_mock()

    def test_event_listener_invalid_type(self, mock_client):
        """Test the event listener when an attribute has an invalid type."""
        self._setup(mock_client)

        # map of HA State to valid influxdb [state, value] fields
        valid = {
            "1": [None, 1],
            "1.0": [None, 1.0],
            STATE_ON: [STATE_ON, 1],
            STATE_OFF: [STATE_OFF, 0],
            STATE_STANDBY: [STATE_STANDBY, None],
            "foo": ["foo", None],
        }
        for in_, out in valid.items():
            attrs = {
                "unit_of_measurement": "foobars",
                "longitude": "1.1",
                "latitude": "2.2",
                "invalid_attribute": ["value1", "value2"],
            }
            state = mock.MagicMock(
                state=in_,
                domain="fake",
                entity_id="fake.entity-id",
                object_id="entity",
                attributes=attrs,
            )
            event = mock.MagicMock(data={"new_state": state}, time_fired=12345)
            body = [
                {
                    "measurement": "foobars",
                    "tags": {"domain": "fake", "entity_id": "entity"},
                    "time": 12345,
                    "fields": {
                        "longitude": 1.1,
                        "latitude": 2.2,
                        "invalid_attribute_str": "['value1', 'value2']",
                    },
                }
            ]
            if out[0] is not None:
                body[0]["fields"]["state"] = out[0]
            if out[1] is not None:
                body[0]["fields"]["value"] = out[1]

            self.handler_method(event)
            self.hass.data[influxdb.DOMAIN].block_till_done()
            assert mock_client.return_value.write_points.call_count == 1
            assert mock_client.return_value.write_points.call_args == mock.call(body)
            mock_client.return_value.write_points.reset_mock()

    def test_event_listener_default_measurement(self, mock_client):
        """Test the event listener with a default measurement."""
        config = {
            "influxdb": {
                "host": "host",
                "username": "user",
                "password": "pass",
                "default_measurement": "state",
                "exclude": {"entities": ["fake.blacklisted"]},
            }
        }
        assert setup_component(self.hass, influxdb.DOMAIN, config)
        self.handler_method = self.hass.bus.listen.call_args_list[0][0][1]
        mock_client.return_value.write_points.reset_mock()

        for entity_id in ("ok", "blacklisted"):
            state = mock.MagicMock(
                state=1,
                domain="fake",
                entity_id="fake.{}".format(entity_id),
                object_id=entity_id,
                attributes={},
            )
            event = mock.MagicMock(data={"new_state": state}, time_fired=12345)
            body = [
                {
                    "measurement": "state",
                    "tags": {"domain": "fake", "entity_id": entity_id},
                    "time": 12345,
                    "fields": {"value": 1},
                }
            ]
            self.handler_method(event)
            self.hass.data[influxdb.DOMAIN].block_till_done()
            if entity_id == "ok":
                assert mock_client.return_value.write_points.call_count == 1
                assert mock_client.return_value.write_points.call_args == mock.call(
                    body
                )
            else:
                assert not mock_client.return_value.write_points.called
            mock_client.return_value.write_points.reset_mock()

    def test_event_listener_unit_of_measurement_field(self, mock_client):
        """Test the event listener for unit of measurement field."""
        config = {
            "influxdb": {
                "host": "host",
                "username": "user",
                "password": "pass",
                "override_measurement": "state",
            }
        }
        assert setup_component(self.hass, influxdb.DOMAIN, config)
        self.handler_method = self.hass.bus.listen.call_args_list[0][0][1]
        mock_client.return_value.write_points.reset_mock()

        attrs = {"unit_of_measurement": "foobars"}
        state = mock.MagicMock(
            state="foo",
            domain="fake",
            entity_id="fake.entity-id",
            object_id="entity",
            attributes=attrs,
        )
        event = mock.MagicMock(data={"new_state": state}, time_fired=12345)
        body = [
            {
                "measurement": "state",
                "tags": {"domain": "fake", "entity_id": "entity"},
                "time": 12345,
                "fields": {"state": "foo", "unit_of_measurement_str": "foobars"},
            }
        ]
        self.handler_method(event)
        self.hass.data[influxdb.DOMAIN].block_till_done()
        assert mock_client.return_value.write_points.call_count == 1
        assert mock_client.return_value.write_points.call_args == mock.call(body)
        mock_client.return_value.write_points.reset_mock()

    def test_event_listener_tags_attributes(self, mock_client):
        """Test the event listener when some attributes should be tags."""
        config = {
            "influxdb": {
                "host": "host",
                "username": "user",
                "password": "pass",
                "tags_attributes": ["friendly_fake"],
            }
        }
        assert setup_component(self.hass, influxdb.DOMAIN, config)
        self.handler_method = self.hass.bus.listen.call_args_list[0][0][1]
        mock_client.return_value.write_points.reset_mock()

        attrs = {"friendly_fake": "tag_str", "field_fake": "field_str"}
        state = mock.MagicMock(
            state=1,
            domain="fake",
            entity_id="fake.something",
            object_id="something",
            attributes=attrs,
        )
        event = mock.MagicMock(data={"new_state": state}, time_fired=12345)
        body = [
            {
                "measurement": "fake.something",
                "tags": {
                    "domain": "fake",
                    "entity_id": "something",
                    "friendly_fake": "tag_str",
                },
                "time": 12345,
                "fields": {"value": 1, "field_fake_str": "field_str"},
            }
        ]
        self.handler_method(event)
        self.hass.data[influxdb.DOMAIN].block_till_done()
        assert mock_client.return_value.write_points.call_count == 1
        assert mock_client.return_value.write_points.call_args == mock.call(body)
        mock_client.return_value.write_points.reset_mock()

    def test_event_listener_component_override_measurement(self, mock_client):
        """Test the event listener with overridden measurements."""
        config = {
            "influxdb": {
                "host": "host",
                "username": "user",
                "password": "pass",
                "component_config": {
                    "sensor.fake_humidity": {"override_measurement": "humidity"}
                },
                "component_config_glob": {
                    "binary_sensor.*motion": {"override_measurement": "motion"}
                },
                "component_config_domain": {
                    "climate": {"override_measurement": "hvac"}
                },
            }
        }
        assert setup_component(self.hass, influxdb.DOMAIN, config)
        self.handler_method = self.hass.bus.listen.call_args_list[0][0][1]
        mock_client.return_value.write_points.reset_mock()

        test_components = [
            {"domain": "sensor", "id": "fake_humidity", "res": "humidity"},
            {"domain": "binary_sensor", "id": "fake_motion", "res": "motion"},
            {"domain": "climate", "id": "fake_thermostat", "res": "hvac"},
            {"domain": "other", "id": "just_fake", "res": "other.just_fake"},
        ]
        for comp in test_components:
            state = mock.MagicMock(
                state=1,
                domain=comp["domain"],
                entity_id=comp["domain"] + "." + comp["id"],
                object_id=comp["id"],
                attributes={},
            )
            event = mock.MagicMock(data={"new_state": state}, time_fired=12345)
            body = [
                {
                    "measurement": comp["res"],
                    "tags": {"domain": comp["domain"], "entity_id": comp["id"]},
                    "time": 12345,
                    "fields": {"value": 1},
                }
            ]
            self.handler_method(event)
            self.hass.data[influxdb.DOMAIN].block_till_done()
            assert mock_client.return_value.write_points.call_count == 1
            assert mock_client.return_value.write_points.call_args == mock.call(body)
            mock_client.return_value.write_points.reset_mock()

    def test_scheduled_write(self, mock_client):
        """Test the event listener to retry after write failures."""
        config = {
            "influxdb": {
                "host": "host",
                "username": "user",
                "password": "pass",
                "max_retries": 1,
            }
        }
        assert setup_component(self.hass, influxdb.DOMAIN, config)
        self.handler_method = self.hass.bus.listen.call_args_list[0][0][1]
        mock_client.return_value.write_points.reset_mock()

        state = mock.MagicMock(
            state=1,
            domain="fake",
            entity_id="entity.id",
            object_id="entity",
            attributes={},
        )
        event = mock.MagicMock(data={"new_state": state}, time_fired=12345)
        mock_client.return_value.write_points.side_effect = IOError("foo")

        # Write fails
        with mock.patch.object(influxdb.time, "sleep") as mock_sleep:
            self.handler_method(event)
            self.hass.data[influxdb.DOMAIN].block_till_done()
            assert mock_sleep.called
        json_data = mock_client.return_value.write_points.call_args[0][0]
        assert mock_client.return_value.write_points.call_count == 2
        mock_client.return_value.write_points.assert_called_with(json_data)

        # Write works again
        mock_client.return_value.write_points.side_effect = None
        with mock.patch.object(influxdb.time, "sleep") as mock_sleep:
            self.handler_method(event)
            self.hass.data[influxdb.DOMAIN].block_till_done()
            assert not mock_sleep.called
        assert mock_client.return_value.write_points.call_count == 3

    def test_queue_backlog_full(self, mock_client):
        """Test the event listener to drop old events."""
        self._setup(mock_client)

        state = mock.MagicMock(
            state=1,
            domain="fake",
            entity_id="entity.id",
            object_id="entity",
            attributes={},
        )
        event = mock.MagicMock(data={"new_state": state}, time_fired=12345)

        monotonic_time = 0

        def fast_monotonic():
            """Monotonic time that ticks fast enough to cause a timeout."""
            nonlocal monotonic_time
            monotonic_time += 60
            return monotonic_time

        with mock.patch(
            "homeassistant.components.influxdb.time.monotonic", new=fast_monotonic
        ):
            self.handler_method(event)
            self.hass.data[influxdb.DOMAIN].block_till_done()

            assert mock_client.return_value.write_points.call_count == 0

        mock_client.return_value.write_points.reset_mock()
