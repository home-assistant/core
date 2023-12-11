"""The tests for the Command line sensor platform."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import subprocess
from typing import Any
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant import setup
from homeassistant.components.command_line import DOMAIN
from homeassistant.components.command_line.sensor import CommandSensor
from homeassistant.components.homeassistant import (
    DOMAIN as HA_DOMAIN,
    SERVICE_UPDATE_ENTITY,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from tests.common import async_fire_time_changed


@pytest.mark.parametrize(
    "get_config",
    [
        {
            "command_line": [
                {
                    "sensor": {
                        "name": "Test",
                        "command": "echo 5",
                        "unit_of_measurement": "in",
                    }
                }
            ]
        }
    ],
)
async def test_setup_integration_yaml(
    hass: HomeAssistant, load_yaml_integration: None
) -> None:
    """Test sensor setup."""

    entity_state = hass.states.get("sensor.test")
    assert entity_state
    assert entity_state.state == "5"
    assert entity_state.name == "Test"
    assert entity_state.attributes["unit_of_measurement"] == "in"


@pytest.mark.parametrize(
    "get_config",
    [
        {
            "command_line": [
                {
                    "sensor": {
                        "name": "Test",
                        "command": "echo 50",
                        "unit_of_measurement": "in",
                        "value_template": "{{ value | multiply(0.1) }}",
                        "icon": "mdi:console",
                    }
                }
            ]
        }
    ],
)
async def test_template(hass: HomeAssistant, load_yaml_integration: None) -> None:
    """Test command sensor with template."""

    entity_state = hass.states.get("sensor.test")
    assert entity_state
    assert float(entity_state.state) == 5
    assert entity_state.attributes.get("icon") == "mdi:console"


@pytest.mark.parametrize(
    "get_config",
    [
        {
            "command_line": [
                {
                    "sensor": {
                        "name": "Test",
                        "command": "echo {{ states.sensor.input_sensor.state }}",
                    }
                }
            ]
        }
    ],
)
async def test_template_render(
    hass: HomeAssistant, load_yaml_integration: None
) -> None:
    """Ensure command with templates get rendered properly."""
    hass.states.async_set("sensor.input_sensor", "sensor_value")

    # Give time for template to load
    async_fire_time_changed(
        hass,
        dt_util.utcnow() + timedelta(minutes=1),
    )
    await hass.async_block_till_done()

    entity_state = hass.states.get("sensor.test")
    assert entity_state
    assert entity_state.state == "sensor_value"


async def test_template_render_with_quote(hass: HomeAssistant) -> None:
    """Ensure command with templates and quotes get rendered properly."""
    hass.states.async_set("sensor.input_sensor", "sensor_value")
    await setup.async_setup_component(
        hass,
        DOMAIN,
        {
            "command_line": [
                {
                    "sensor": {
                        "name": "Test",
                        "command": 'echo "{{ states.sensor.input_sensor.state }}" "3 4"',
                    }
                }
            ]
        },
    )
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.command_line.utils.subprocess.check_output",
        return_value=b"Works\n",
    ) as check_output:
        # Give time for template to load
        async_fire_time_changed(
            hass,
            dt_util.utcnow() + timedelta(minutes=1),
        )
        await hass.async_block_till_done()

        assert len(check_output.mock_calls) == 1
        check_output.assert_called_with(
            'echo "sensor_value" "3 4"',
            shell=True,  # noqa: S604 # shell by design
            timeout=15,
            close_fds=False,
        )


@pytest.mark.parametrize(
    "get_config",
    [
        {
            "command_line": [
                {
                    "sensor": {
                        "name": "Test",
                        "command": "echo {{ this template doesn't parse",
                    }
                }
            ]
        }
    ],
)
async def test_bad_template_render(
    caplog: pytest.LogCaptureFixture, hass: HomeAssistant, get_config: dict[str, Any]
) -> None:
    """Test rendering a broken template."""
    await setup.async_setup_component(
        hass,
        DOMAIN,
        get_config,
    )
    await hass.async_block_till_done()

    assert "Error rendering command template" in caplog.text


@pytest.mark.parametrize(
    "get_config",
    [
        {
            "command_line": [
                {
                    "sensor": {
                        "name": "Test",
                        "command": "asdfasdf",
                    }
                }
            ]
        }
    ],
)
async def test_bad_command(hass: HomeAssistant, get_config: dict[str, Any]) -> None:
    """Test bad command."""
    await setup.async_setup_component(
        hass,
        DOMAIN,
        get_config,
    )
    await hass.async_block_till_done()

    entity_state = hass.states.get("sensor.test")
    assert entity_state
    assert entity_state.state == "unknown"


@pytest.mark.parametrize(
    "get_config",
    [
        {
            "command_line": [
                {
                    "sensor": {
                        "name": "Test",
                        "command": "exit 33",
                    }
                }
            ]
        }
    ],
)
async def test_return_code(
    caplog: pytest.LogCaptureFixture, hass: HomeAssistant, get_config: dict[str, Any]
) -> None:
    """Test that an error return code is logged."""
    await setup.async_setup_component(
        hass,
        DOMAIN,
        get_config,
    )
    await hass.async_block_till_done()

    assert "return code 33" in caplog.text


@pytest.mark.parametrize(
    "get_config",
    [
        {
            "command_line": [
                {
                    "sensor": {
                        "name": "Test",
                        "command": (
                            'echo { \\"key\\": \\"some_json_value\\", \\"another_key\\": '
                            '\\"another_json_value\\", \\"key_three\\": \\"value_three\\" }'
                        ),
                        "json_attributes": ["key", "another_key", "key_three"],
                    }
                }
            ]
        }
    ],
)
async def test_update_with_json_attrs(
    hass: HomeAssistant, load_yaml_integration: None
) -> None:
    """Test attributes get extracted from a JSON result."""
    entity_state = hass.states.get("sensor.test")
    assert entity_state
    assert entity_state.state == "unknown"
    assert entity_state.attributes["key"] == "some_json_value"
    assert entity_state.attributes["another_key"] == "another_json_value"
    assert entity_state.attributes["key_three"] == "value_three"


@pytest.mark.parametrize(
    "get_config",
    [
        {
            "command_line": [
                {
                    "sensor": {
                        "name": "Test",
                        "command": (
                            'echo { \\"key\\": \\"some_json_value\\", \\"another_key\\": '
                            '\\"another_json_value\\", \\"key_three\\": \\"value_three\\" }'
                        ),
                        "json_attributes": ["key", "another_key", "key_three"],
                        "value_template": '{{ value_json["key"] }}',
                    }
                }
            ]
        }
    ],
)
async def test_update_with_json_attrs_and_value_template(
    hass: HomeAssistant, load_yaml_integration: None
) -> None:
    """Test json_attributes can be used together with value_template."""
    entity_state = hass.states.get("sensor.test")
    assert entity_state
    assert entity_state.state == "some_json_value"
    assert entity_state.attributes["key"] == "some_json_value"
    assert entity_state.attributes["another_key"] == "another_json_value"
    assert entity_state.attributes["key_three"] == "value_three"


@pytest.mark.parametrize(
    "get_config",
    [
        {
            "command_line": [
                {
                    "sensor": {
                        "name": "Test",
                        "command": "echo",
                        "json_attributes": ["key"],
                    }
                }
            ]
        }
    ],
)
async def test_update_with_json_attrs_no_data(
    caplog: pytest.LogCaptureFixture, hass: HomeAssistant, get_config: dict[str, Any]
) -> None:
    """Test attributes when no JSON result fetched."""
    await setup.async_setup_component(
        hass,
        DOMAIN,
        get_config,
    )
    await hass.async_block_till_done()

    entity_state = hass.states.get("sensor.test")
    assert entity_state
    assert "key" not in entity_state.attributes
    assert "Empty reply found when expecting JSON data" in caplog.text


@pytest.mark.parametrize(
    "get_config",
    [
        {
            "command_line": [
                {
                    "sensor": {
                        "name": "Test",
                        "command": "echo [1, 2, 3]",
                        "json_attributes": ["key"],
                    }
                }
            ]
        }
    ],
)
async def test_update_with_json_attrs_not_dict(
    caplog: pytest.LogCaptureFixture, hass: HomeAssistant, get_config: dict[str, Any]
) -> None:
    """Test attributes when the return value not a dict."""
    await setup.async_setup_component(
        hass,
        DOMAIN,
        get_config,
    )
    await hass.async_block_till_done()

    entity_state = hass.states.get("sensor.test")
    assert entity_state
    assert "key" not in entity_state.attributes
    assert "JSON result was not a dictionary" in caplog.text


@pytest.mark.parametrize(
    "get_config",
    [
        {
            "command_line": [
                {
                    "sensor": {
                        "name": "Test",
                        "command": "echo This is text rather than JSON data.",
                        "json_attributes": ["key"],
                    }
                }
            ]
        }
    ],
)
async def test_update_with_json_attrs_bad_json(
    caplog: pytest.LogCaptureFixture, hass: HomeAssistant, get_config: dict[str, Any]
) -> None:
    """Test attributes when the return value is invalid JSON."""
    await setup.async_setup_component(
        hass,
        DOMAIN,
        get_config,
    )
    await hass.async_block_till_done()

    entity_state = hass.states.get("sensor.test")
    assert entity_state
    assert "key" not in entity_state.attributes
    assert "Unable to parse output as JSON" in caplog.text


@pytest.mark.parametrize(
    "get_config",
    [
        {
            "command_line": [
                {
                    "sensor": {
                        "name": "Test",
                        "command": (
                            'echo { \\"key\\": \\"some_json_value\\", \\"another_key\\": '
                            '\\"another_json_value\\", \\"key_three\\": \\"value_three\\" }'
                        ),
                        "json_attributes": [
                            "key",
                            "another_key",
                            "key_three",
                            "missing_key",
                        ],
                    }
                }
            ]
        }
    ],
)
async def test_update_with_missing_json_attrs(
    caplog: pytest.LogCaptureFixture, hass: HomeAssistant, load_yaml_integration: None
) -> None:
    """Test attributes when an expected key is missing."""

    entity_state = hass.states.get("sensor.test")
    assert entity_state
    assert entity_state.attributes["key"] == "some_json_value"
    assert entity_state.attributes["another_key"] == "another_json_value"
    assert entity_state.attributes["key_three"] == "value_three"
    assert "missing_key" not in entity_state.attributes


@pytest.mark.parametrize(
    "get_config",
    [
        {
            "command_line": [
                {
                    "sensor": {
                        "name": "Test",
                        "command": (
                            'echo { \\"key\\": \\"some_json_value\\", \\"another_key\\": '
                            '\\"another_json_value\\", \\"key_three\\": \\"value_three\\" }'
                        ),
                        "json_attributes": ["key", "another_key"],
                    }
                }
            ]
        }
    ],
)
async def test_update_with_unnecessary_json_attrs(
    caplog: pytest.LogCaptureFixture, hass: HomeAssistant, load_yaml_integration: None
) -> None:
    """Test attributes when an expected key is missing."""

    entity_state = hass.states.get("sensor.test")
    assert entity_state
    assert entity_state.attributes["key"] == "some_json_value"
    assert entity_state.attributes["another_key"] == "another_json_value"
    assert "key_three" not in entity_state.attributes


@pytest.mark.parametrize(
    "get_config",
    [
        {
            "command_line": [
                {
                    "sensor": {
                        "name": "Test",
                        "unique_id": "unique",
                        "command": "echo 0",
                    }
                },
                {
                    "sensor": {
                        "name": "Test",
                        "unique_id": "not-so-unique-anymore",
                        "command": "echo 1",
                    }
                },
                {
                    "sensor": {
                        "name": "Test",
                        "unique_id": "not-so-unique-anymore",
                        "command": "echo 2",
                    },
                },
            ]
        }
    ],
)
async def test_unique_id(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, load_yaml_integration: None
) -> None:
    """Test unique_id option and if it only creates one sensor per id."""

    assert len(hass.states.async_all()) == 2

    assert len(entity_registry.entities) == 2
    assert entity_registry.async_get_entity_id("sensor", "command_line", "unique")
    assert entity_registry.async_get_entity_id(
        "sensor", "command_line", "not-so-unique-anymore"
    )


async def test_updating_to_often(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test handling updating when command already running."""
    wait_till_event = asyncio.Event()
    wait_till_event.set()
    called = []

    class MockCommandSensor(CommandSensor):
        """Mock entity that updates."""

        async def _async_update(self) -> None:
            """Update entity."""
            called.append(1)
            # Wait till event is set
            await wait_till_event.wait()

    with patch(
        "homeassistant.components.command_line.sensor.CommandSensor",
        side_effect=MockCommandSensor,
    ):
        await setup.async_setup_component(
            hass,
            DOMAIN,
            {
                "command_line": [
                    {
                        "sensor": {
                            "name": "Test",
                            "command": "echo 1",
                            "scan_interval": 10,
                        }
                    }
                ]
            },
        )
        await hass.async_block_till_done()

    assert called
    async_fire_time_changed(hass, dt_util.now() + timedelta(seconds=15))
    wait_till_event.set()
    await asyncio.sleep(0)

    assert (
        "Updating Command Line Sensor Test took longer than the scheduled update interval"
        not in caplog.text
    )

    # Simulate update takes too long
    wait_till_event.clear()
    async_fire_time_changed(hass, dt_util.now() + timedelta(seconds=10))
    await asyncio.sleep(0)
    async_fire_time_changed(hass, dt_util.now() + timedelta(seconds=10))
    wait_till_event.set()
    await asyncio.sleep(0)

    assert (
        "Updating Command Line Sensor Test took longer than the scheduled update interval"
        in caplog.text
    )


async def test_updating_manually(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test handling manual updating using homeassistant udate_entity service."""
    await setup.async_setup_component(hass, HA_DOMAIN, {})
    called = []

    class MockCommandSensor(CommandSensor):
        """Mock entity that updates."""

        async def _async_update(self) -> None:
            """Update slow."""
            called.append(1)

    with patch(
        "homeassistant.components.command_line.sensor.CommandSensor",
        side_effect=MockCommandSensor,
    ):
        await setup.async_setup_component(
            hass,
            DOMAIN,
            {
                "command_line": [
                    {
                        "sensor": {
                            "name": "Test",
                            "command": "echo 1",
                            "scan_interval": 10,
                        }
                    }
                ]
            },
        )
        await hass.async_block_till_done()

    assert called
    called.clear()

    await hass.services.async_call(
        HA_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: ["sensor.test"]},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert called


@pytest.mark.parametrize(
    "get_config",
    [
        {
            "command_line": [
                {
                    "sensor": {
                        "name": "Test",
                        "command": "echo 2022-12-22T13:15:30Z",
                        "device_class": "timestamp",
                    }
                }
            ]
        }
    ],
)
async def test_scrape_sensor_device_timestamp(
    hass: HomeAssistant, load_yaml_integration: None
) -> None:
    """Test Command Line sensor with a device of type TIMESTAMP."""
    entity_state = hass.states.get("sensor.test")
    assert entity_state
    assert entity_state.state == "2022-12-22T13:15:30+00:00"


@pytest.mark.parametrize(
    "get_config",
    [
        {
            "command_line": [
                {
                    "sensor": {
                        "name": "Test",
                        "command": "echo January 17, 2022",
                        "device_class": "date",
                        "value_template": "{{ strptime(value, '%B %d, %Y').strftime('%Y-%m-%d') }}",
                    }
                }
            ]
        }
    ],
)
async def test_scrape_sensor_device_date(
    hass: HomeAssistant, load_yaml_integration: None
) -> None:
    """Test Command Line sensor with a device of type DATE."""
    entity_state = hass.states.get("sensor.test")
    assert entity_state
    assert entity_state.state == "2022-01-17"


async def test_template_not_error_when_data_is_none(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test command sensor with template not logging error when data is None."""

    with patch(
        "homeassistant.components.command_line.utils.subprocess.check_output",
        side_effect=subprocess.CalledProcessError,
    ):
        await setup.async_setup_component(
            hass,
            DOMAIN,
            {
                "command_line": [
                    {
                        "sensor": {
                            "name": "Test",
                            "command": "failed command",
                            "unit_of_measurement": "MB",
                            "value_template": "{{ (value.split('\t')[0]|int(0)/1000)|round(3) }}",
                        }
                    }
                ]
            },
        )
    await hass.async_block_till_done()

    entity_state = hass.states.get("sensor.test")
    assert entity_state
    assert entity_state.state == STATE_UNKNOWN

    assert (
        "Template variable error: 'None' has no attribute 'split' when rendering"
        not in caplog.text
    )


@pytest.mark.parametrize(
    "get_config",
    [
        {
            "command_line": [
                {
                    "sensor": {
                        "name": "Test",
                        "command": "echo January 17, 2022",
                        "device_class": "date",
                        "value_template": "{{ strptime(value, '%B %d, %Y').strftime('%Y-%m-%d') }}",
                        "availability": '{{ states("sensor.input1")=="on" }}',
                    }
                }
            ]
        }
    ],
)
async def test_availability(
    hass: HomeAssistant,
    load_yaml_integration: None,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test availability."""

    hass.states.async_set("sensor.input1", "on")
    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    entity_state = hass.states.get("sensor.test")
    assert entity_state
    assert entity_state.state == "2022-01-17"

    hass.states.async_set("sensor.input1", "off")
    await hass.async_block_till_done()
    with patch(
        "homeassistant.components.command_line.utils.subprocess.check_output",
        return_value=b"January 17, 2022",
    ):
        freezer.tick(timedelta(minutes=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    entity_state = hass.states.get("sensor.test")
    assert entity_state
    assert entity_state.state == STATE_UNAVAILABLE
