"""The test for the Anomaly sensor platform."""
from datetime import timedelta
from os import path

from homeassistant import config as hass_config, setup
from homeassistant.components.anomaly import DOMAIN
from homeassistant.const import SERVICE_RELOAD
import homeassistant.util.dt as dt_util

from tests.async_mock import patch
from tests.common import assert_setup_component, get_test_home_assistant


class TestAnomalyBinarySensor:
    """Test the anomaly sensor."""

    hass = None

    def setup_method(self, method):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()

    def test_up_and_off(self):
        """Test up anomaly."""
        assert setup.setup_component(
            self.hass,
            "binary_sensor",
            {
                "binary_sensor": {
                    "platform": "anomaly",
                    "sensors": {
                        "test_anomaly_sensor": {
                            "entity_id": "sensor.test_state",
                            "min_change_amount": 3,
                        }
                    },
                }
            },
        )
        self.hass.block_till_done()

        self.hass.states.set("sensor.test_state", "1")
        self.hass.block_till_done()
        self.hass.states.set("sensor.test_state", "10")
        self.hass.block_till_done()
        state = self.hass.states.get("binary_sensor.test_anomaly_sensor")
        assert state.state == "on"
        self.hass.states.set("sensor.test_state", "11")
        self.hass.block_till_done()
        self.hass.states.set("sensor.test_state", "10")
        self.hass.block_till_done()
        state = self.hass.states.get("binary_sensor.test_anomaly_sensor")
        assert state.state == "off"

    def test_down_and_off(self):
        """Test down anomaly."""
        assert setup.setup_component(
            self.hass,
            "binary_sensor",
            {
                "binary_sensor": {
                    "platform": "anomaly",
                    "sensors": {
                        "test_anomaly_sensor": {
                            "entity_id": "sensor.test_state",
                            "min_change_amount": 3,
                        }
                    },
                }
            },
        )
        self.hass.block_till_done()

        self.hass.states.set("sensor.test_state", "10")
        self.hass.block_till_done()
        self.hass.states.set("sensor.test_state", "1")
        self.hass.block_till_done()
        state = self.hass.states.get("binary_sensor.test_anomaly_sensor")
        assert state.state == "on"
        self.hass.states.set("sensor.test_state", "0")
        self.hass.block_till_done()
        self.hass.states.set("sensor.test_state", "1")
        self.hass.block_till_done()
        state = self.hass.states.get("binary_sensor.test_anomaly_sensor")
        assert state.state == "off"

    def test_positive_only(self):
        """Test up anomaly."""
        assert setup.setup_component(
            self.hass,
            "binary_sensor",
            {
                "binary_sensor": {
                    "platform": "anomaly",
                    "sensors": {
                        "test_anomaly_sensor": {
                            "entity_id": "sensor.test_state",
                            "min_change_amount": 3,
                            "positive_only": True,
                        }
                    },
                }
            },
        )
        self.hass.block_till_done()

        self.hass.states.set("sensor.test_state", "0")
        self.hass.block_till_done()
        self.hass.states.set("sensor.test_state", "1")
        self.hass.block_till_done()
        state = self.hass.states.get("binary_sensor.test_anomaly_sensor")
        assert state.state == "off"
        self.hass.states.set("sensor.test_state", "11")
        self.hass.block_till_done()
        state = self.hass.states.get("binary_sensor.test_anomaly_sensor")
        assert state.state == "on"
        self.hass.states.set("sensor.test_state", "11")
        self.hass.block_till_done()
        self.hass.states.set("sensor.test_state", "1")
        self.hass.block_till_done()
        state = self.hass.states.get("binary_sensor.test_anomaly_sensor")
        assert state.state == "off"

    def test_negative_only(self):
        """Test up anomaly."""
        assert setup.setup_component(
            self.hass,
            "binary_sensor",
            {
                "binary_sensor": {
                    "platform": "anomaly",
                    "sensors": {
                        "test_anomaly_sensor": {
                            "entity_id": "sensor.test_state",
                            "min_change_amount": 3,
                            "negative_only": True,
                        }
                    },
                }
            },
        )
        self.hass.block_till_done()

        self.hass.states.set("sensor.test_state", "1")
        self.hass.block_till_done()
        self.hass.states.set("sensor.test_state", "10")
        self.hass.block_till_done()
        state = self.hass.states.get("binary_sensor.test_anomaly_sensor")
        assert state.state == "off"
        self.hass.states.set("sensor.test_state", "11")
        self.hass.block_till_done()
        self.hass.states.set("sensor.test_state", "0")
        self.hass.block_till_done()
        state = self.hass.states.get("binary_sensor.test_anomaly_sensor")
        assert state.state == "on"
        self.hass.states.set("sensor.test_state", "1")
        self.hass.block_till_done()
        self.hass.states.set("sensor.test_state", "0")
        self.hass.block_till_done()
        state = self.hass.states.get("binary_sensor.test_anomaly_sensor")
        assert state.state == "off"

    def test_up_using_amount(self):
        """Test up anomaly using many samples."""
        assert setup.setup_component(
            self.hass,
            "binary_sensor",
            {
                "binary_sensor": {
                    "platform": "anomaly",
                    "sensors": {
                        "test_anomaly_sensor": {
                            "entity_id": "sensor.test_state",
                            "max_samples": 3,
                            "max_trailing_samples": 7,
                            "min_change_amount": 5,
                        }
                    },
                }
            },
        )
        self.hass.block_till_done()

        now = dt_util.utcnow()

        state = self.hass.states.get("binary_sensor.test_anomaly_sensor")
        assert state.state == "off"

        for val in [1, 2, 3, 30, 31, 32]:
            with patch("homeassistant.util.dt.utcnow", return_value=now):
                self.hass.states.set("sensor.test_state", val)
            self.hass.block_till_done()
            now += timedelta(seconds=2)

        state = self.hass.states.get("binary_sensor.test_anomaly_sensor")
        assert state.state == "on"

        # have to change state value, otherwise sample will lost
        for val in [30, 31, 32, 33]:
            with patch("homeassistant.util.dt.utcnow", return_value=now):
                self.hass.states.set("sensor.test_state", val)
            self.hass.block_till_done()
            now += timedelta(seconds=2)

        state = self.hass.states.get("binary_sensor.test_anomaly_sensor")
        assert state.state == "off"

    def test_down_using_amount(self):
        """Test down anomaly using many samples."""
        assert setup.setup_component(
            self.hass,
            "binary_sensor",
            {
                "binary_sensor": {
                    "platform": "anomaly",
                    "sensors": {
                        "test_anomaly_sensor": {
                            "entity_id": "sensor.test_state",
                            "max_samples": 3,
                            "max_trailing_samples": 7,
                            "min_change_amount": 5,
                        }
                    },
                }
            },
        )
        self.hass.block_till_done()

        now = dt_util.utcnow()
        for val in [30, 31, 32, 33, 1, 2, 3]:
            with patch("homeassistant.util.dt.utcnow", return_value=now):
                self.hass.states.set("sensor.test_state", val)
            self.hass.block_till_done()
            now += timedelta(seconds=2)

        state = self.hass.states.get("binary_sensor.test_anomaly_sensor")
        assert state.state == "on"

        for val in [0, 1, 2, 3]:
            with patch("homeassistant.util.dt.utcnow", return_value=now):
                self.hass.states.set("sensor.test_state", val)
            self.hass.block_till_done()
            now += timedelta(seconds=2)

        state = self.hass.states.get("binary_sensor.test_anomaly_sensor")
        assert state.state == "off"

    def test_invert_up_and_on(self):
        """Test up anomly with invert."""
        assert setup.setup_component(
            self.hass,
            "binary_sensor",
            {
                "binary_sensor": {
                    "platform": "anomaly",
                    "sensors": {
                        "test_anomaly_sensor": {
                            "entity_id": "sensor.test_state",
                            "invert": "Yes",
                            "min_change_amount": 3,
                        }
                    },
                }
            },
        )
        self.hass.block_till_done()

        self.hass.states.set("sensor.test_state", "1")
        self.hass.block_till_done()
        self.hass.states.set("sensor.test_state", "10")
        self.hass.block_till_done()
        state = self.hass.states.get("binary_sensor.test_anomaly_sensor")
        assert state.state == "off"
        self.hass.states.set("sensor.test_state", "11")
        self.hass.block_till_done()
        self.hass.states.set("sensor.test_state", "10")
        self.hass.block_till_done()
        state = self.hass.states.get("binary_sensor.test_anomaly_sensor")
        assert state.state == "on"

    def test_invert_down_and_on(self):
        """Test down anomaly with invert."""
        assert setup.setup_component(
            self.hass,
            "binary_sensor",
            {
                "binary_sensor": {
                    "platform": "anomaly",
                    "sensors": {
                        "test_anomaly_sensor": {
                            "entity_id": "sensor.test_state",
                            "invert": "Yes",
                            "min_change_amount": 3,
                        }
                    },
                }
            },
        )
        self.hass.block_till_done()

        self.hass.states.set("sensor.test_state", "10")
        self.hass.block_till_done()
        self.hass.states.set("sensor.test_state", "1")
        self.hass.block_till_done()
        state = self.hass.states.get("binary_sensor.test_anomaly_sensor")
        assert state.state == "off"
        self.hass.states.set("sensor.test_state", "0")
        self.hass.block_till_done()
        self.hass.states.set("sensor.test_state", "1")
        self.hass.block_till_done()
        state = self.hass.states.get("binary_sensor.test_anomaly_sensor")
        assert state.state == "on"

    def test_attribute_up(self):
        """Test attribute up anomaly."""
        assert setup.setup_component(
            self.hass,
            "binary_sensor",
            {
                "binary_sensor": {
                    "platform": "anomaly",
                    "sensors": {
                        "test_anomaly_sensor": {
                            "entity_id": "sensor.test_state",
                            "min_change_amount": 3,
                            "attribute": "attr",
                        }
                    },
                }
            },
        )
        self.hass.block_till_done()
        self.hass.states.set("sensor.test_state", "State", {"attr": "1"})
        self.hass.block_till_done()
        self.hass.states.set("sensor.test_state", "State", {"attr": "10"})
        self.hass.block_till_done()
        state = self.hass.states.get("binary_sensor.test_anomaly_sensor")
        assert state.state == "on"

    def test_attribute_down(self):
        """Test attribute down anomaly."""
        assert setup.setup_component(
            self.hass,
            "binary_sensor",
            {
                "binary_sensor": {
                    "platform": "anomaly",
                    "sensors": {
                        "test_anomaly_sensor": {
                            "entity_id": "sensor.test_state",
                            "min_change_amount": 3,
                            "attribute": "attr",
                        }
                    },
                }
            },
        )
        self.hass.block_till_done()

        self.hass.states.set("sensor.test_state", "State", {"attr": "10"})
        self.hass.block_till_done()
        self.hass.states.set("sensor.test_state", "State", {"attr": "1"})
        self.hass.block_till_done()
        state = self.hass.states.get("binary_sensor.test_anomaly_sensor")
        assert state.state == "on"

    def test_require_both(self):
        """Test attribute down anomaly."""
        assert setup.setup_component(
            self.hass,
            "binary_sensor",
            {
                "binary_sensor": {
                    "platform": "anomaly",
                    "sensors": {
                        "test_anomaly_sensor": {
                            "entity_id": "sensor.test_state",
                            "min_change_amount": 10,
                            "min_change_percent": 99,
                            "require_both": True,
                        }
                    },
                }
            },
        )
        self.hass.block_till_done()

        self.hass.states.set("sensor.test_state", "0")
        self.hass.block_till_done()
        self.hass.states.set("sensor.test_state", "6")
        self.hass.block_till_done()
        state = self.hass.states.get("binary_sensor.test_anomaly_sensor")
        assert state.attributes.get("change_amount") == 3
        assert state.attributes.get("change_percent") == 100
        assert state.state == "off"
        self.hass.states.set("sensor.test_state", "1000")
        self.hass.block_till_done()
        self.hass.states.set("sensor.test_state", "1050")
        self.hass.block_till_done()
        state = self.hass.states.get("binary_sensor.test_anomaly_sensor")
        assert state.attributes.get("change_amount") == 25
        assert state.attributes.get("change_percent") < 2.5
        assert state.state == "off"
        self.hass.states.set("sensor.test_state", "1000")
        self.hass.block_till_done()
        self.hass.states.set("sensor.test_state", "1")
        self.hass.block_till_done()
        state = self.hass.states.get("binary_sensor.test_anomaly_sensor")
        assert state.state == "on"

    def test_max_samples(self):
        """Test that sample count is limited correctly."""
        assert setup.setup_component(
            self.hass,
            "binary_sensor",
            {
                "binary_sensor": {
                    "platform": "anomaly",
                    "sensors": {
                        "test_anomaly_sensor": {
                            "entity_id": "sensor.test_state",
                            "min_change_amount": 3,
                            "max_samples": 3,
                            "max_trailing_samples": 6,
                            "sample_duration": 7,
                            "trailing_sample_duration": 15,
                        }
                    },
                }
            },
        )
        self.hass.block_till_done()

        for val in [0, 1, 2, 3, 50, 51, 52]:
            self.hass.states.set("sensor.test_state", val)
            self.hass.block_till_done()
        state = self.hass.states.get("binary_sensor.test_anomaly_sensor")
        assert state.state == "on"
        assert state.attributes["sample_count"] == 3
        assert state.attributes["trailing_sample_count"] == 6

    def test_no_data(self):
        """Test that sample count is limited correctly."""
        assert setup.setup_component(
            self.hass,
            "binary_sensor",
            {
                "binary_sensor": {
                    "platform": "anomaly",
                    "sensors": {
                        "test_anomaly_sensor": {
                            "entity_id": "sensor.test_state",
                            "min_change_amount": 3,
                        }
                    },
                }
            },
        )
        self.hass.block_till_done()
        state = self.hass.states.get("binary_sensor.test_anomaly_sensor")
        assert state.state == "off"
        assert state.attributes["sample_count"] == 0
        assert state.attributes["trailing_sample_count"] == 0

    def test_non_numeric(self):
        """Test up anomaly."""
        assert setup.setup_component(
            self.hass,
            "binary_sensor",
            {
                "binary_sensor": {
                    "platform": "anomaly",
                    "sensors": {
                        "test_anomaly_sensor": {"entity_id": "sensor.test_state"}
                    },
                }
            },
        )
        self.hass.block_till_done()

        self.hass.states.set("sensor.test_state", "Non")
        self.hass.block_till_done()
        self.hass.states.set("sensor.test_state", "Numeric")
        self.hass.block_till_done()
        state = self.hass.states.get("binary_sensor.test_anomaly_sensor")
        assert state.state == "off"

    def test_missing_attribute(self):
        """Test attribute down anomaly."""
        assert setup.setup_component(
            self.hass,
            "binary_sensor",
            {
                "binary_sensor": {
                    "platform": "anomaly",
                    "sensors": {
                        "test_anomaly_sensor": {
                            "entity_id": "sensor.test_state",
                            "attribute": "missing",
                        }
                    },
                }
            },
        )
        self.hass.block_till_done()

        self.hass.states.set("sensor.test_state", "State", {"attr": "2"})
        self.hass.block_till_done()
        self.hass.states.set("sensor.test_state", "State", {"attr": "1"})
        self.hass.block_till_done()
        state = self.hass.states.get("binary_sensor.test_anomaly_sensor")
        assert state.state == "off"

    def test_invalid_name_does_not_create(self):
        """Test invalid name."""
        with assert_setup_component(0):
            assert setup.setup_component(
                self.hass,
                "binary_sensor",
                {
                    "binary_sensor": {
                        "platform": "template",
                        "sensors": {
                            "test INVALID sensor": {"entity_id": "sensor.test_state"}
                        },
                    }
                },
            )
        assert self.hass.states.all() == []

    def test_invalid_sensor_does_not_create(self):
        """Test invalid sensor."""
        with assert_setup_component(0):
            assert setup.setup_component(
                self.hass,
                "binary_sensor",
                {
                    "binary_sensor": {
                        "platform": "template",
                        "sensors": {
                            "test_anomaly_sensor": {
                                "not_entity_id": "sensor.test_state"
                            }
                        },
                    }
                },
            )
        assert self.hass.states.all() == []

    def test_no_sensors_does_not_create(self):
        """Test no sensors."""
        with assert_setup_component(0):
            assert setup.setup_component(
                self.hass, "binary_sensor", {"binary_sensor": {"platform": "anomaly"}}
            )
        assert self.hass.states.all() == []


async def test_reload(hass):
    """Verify we can reload anomaly sensors."""
    hass.states.async_set("sensor.test_state", 1234)

    await setup.async_setup_component(
        hass,
        "binary_sensor",
        {
            "binary_sensor": {
                "platform": "anomaly",
                "sensors": {"test_anomaly_sensor": {"entity_id": "sensor.test_state"}},
            }
        },
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 2

    assert hass.states.get("binary_sensor.test_anomaly_sensor")

    yaml_path = path.join(
        _get_fixtures_base_path(),
        "fixtures",
        "anomaly/configuration.yaml",
    )
    with patch.object(hass_config, "YAML_CONFIG_FILE", yaml_path):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RELOAD,
            {},
            blocking=True,
        )
        await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 2

    assert hass.states.get("binary_sensor.test_anomaly_sensor") is None
    assert hass.states.get("binary_sensor.second_test_anomaly_sensor")


def _get_fixtures_base_path():
    return path.dirname(path.dirname(path.dirname(__file__)))
