"""Test Command line component setup process."""

from datetime import timedelta
from unittest.mock import patch

import pytest

from homeassistant import config as hass_config, setup
from homeassistant.components.command_line.const import DOMAIN
from homeassistant.const import SERVICE_RELOAD, STATE_ON, STATE_OPEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.util import dt as dt_util

from . import mock_asyncio_subprocess_run

from tests.common import (
    assert_platform_setup_creates_issue,
    async_fire_time_changed,
    get_fixture_path,
)


@pytest.mark.parametrize(
    "platform_domain",
    [
        "binary_sensor",
        "cover",
        "notify",
        "sensor",
        "switch",
    ],
)
async def test_platform_config_creates_issue(
    hass: HomeAssistant,
    platform_domain: str,
    issue_registry: ir.IssueRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test invalid platform config creates issue and logs a warning."""
    await assert_platform_setup_creates_issue(
        hass,
        platform_domain,
        DOMAIN,
        issue_registry,
        caplog,
    )


async def test_setup_config(hass: HomeAssistant, load_yaml_integration: None) -> None:
    """Test setup from yaml."""

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=10))
    await hass.async_block_till_done(wait_background_tasks=True)

    state_binary_sensor = hass.states.get("binary_sensor.test")
    state_sensor = hass.states.get("sensor.test")
    state_cover = hass.states.get("cover.test")
    state_switch = hass.states.get("switch.test")

    assert state_binary_sensor.state == STATE_ON
    assert state_sensor.state == "5"
    assert state_cover.state == STATE_OPEN
    assert state_switch.state == STATE_ON


async def test_reload_service(
    hass: HomeAssistant, load_yaml_integration: None, caplog: pytest.LogCaptureFixture
) -> None:
    """Test reload serviice."""

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=10))
    await hass.async_block_till_done()

    state_binary_sensor = hass.states.get("binary_sensor.test")
    state_sensor = hass.states.get("sensor.test")
    assert state_binary_sensor.state == STATE_ON
    assert state_sensor.state == "5"

    caplog.clear()

    yaml_path = get_fixture_path("configuration.yaml", "command_line")
    with patch.object(hass_config, "YAML_CONFIG_FILE", yaml_path):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RELOAD,
            {},
            blocking=True,
        )
        await hass.async_block_till_done()

    assert "Loading config" in caplog.text

    state_binary_sensor = hass.states.get("binary_sensor.test")
    state_sensor = hass.states.get("sensor.test")
    assert state_binary_sensor.state == STATE_ON
    assert not state_sensor

    caplog.clear()

    yaml_path = get_fixture_path("configuration_empty.yaml", "command_line")
    with patch.object(hass_config, "YAML_CONFIG_FILE", yaml_path):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RELOAD,
            {},
            blocking=True,
        )
        await hass.async_block_till_done()

    state_binary_sensor = hass.states.get("binary_sensor.test")
    state_sensor = hass.states.get("sensor.test")
    assert not state_binary_sensor
    assert not state_sensor

    assert "Loading config" not in caplog.text


async def test_reload_prunes_stale_template_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """A deprecation issue is pruned on reload when its entity is gone."""
    hass.states.async_set("sensor.input_sensor", "safe_value")
    await setup.async_setup_component(
        hass,
        DOMAIN,
        {
            "command_line": [
                {
                    "sensor": {
                        "name": "Test",
                        "command": "echo {{ states.sensor.input_sensor.state }} | cat",
                    }
                }
            ]
        },
    )
    await hass.async_block_till_done()

    with mock_asyncio_subprocess_run(b"safe_value\n"):
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=1))
        await hass.async_block_till_done(wait_background_tasks=True)

    assert any(
        issue.translation_key == "shell_command_template_deprecation"
        for issue in issue_registry.issues.values()
    )

    yaml_path = get_fixture_path("configuration_empty.yaml", "command_line")
    with patch.object(hass_config, "YAML_CONFIG_FILE", yaml_path):
        await hass.services.async_call(DOMAIN, SERVICE_RELOAD, {}, blocking=True)
        await hass.async_block_till_done()

    assert not any(
        issue.translation_key == "shell_command_template_deprecation"
        for issue in issue_registry.issues.values()
    )


async def test_reload_keeps_valid_template_issue_and_ignore_state(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """A still-valid deprecation issue and its ignore state survive reload."""
    hass.states.async_set("sensor.input_sensor", "safe_value")
    await setup.async_setup_component(
        hass,
        DOMAIN,
        {
            "command_line": [
                {
                    "sensor": {
                        "name": "Test",
                        "command": "echo {{ states.sensor.input_sensor.state }} | cat",
                    }
                }
            ]
        },
    )
    await hass.async_block_till_done()

    with mock_asyncio_subprocess_run(b"safe_value\n"):
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=1))
        await hass.async_block_till_done(wait_background_tasks=True)

    issue = next(
        entry
        for entry in issue_registry.issues.values()
        if entry.translation_key == "shell_command_template_deprecation"
    )
    # The user ignores the issue; a delete-and-recreate would reset this.
    ir.async_ignore_issue(hass, DOMAIN, issue.issue_id, True)
    assert issue_registry.issues[(DOMAIN, issue.issue_id)].dismissed_version

    # Reload with the same entity still configured.
    yaml_path = get_fixture_path("configuration_shell_template.yaml", "command_line")
    with (
        patch.object(hass_config, "YAML_CONFIG_FILE", yaml_path),
        mock_asyncio_subprocess_run(b"safe_value\n"),
    ):
        await hass.services.async_call(DOMAIN, SERVICE_RELOAD, {}, blocking=True)
        await hass.async_block_till_done(wait_background_tasks=True)

    kept_issue = issue_registry.issues.get((DOMAIN, issue.issue_id))
    assert kept_issue is not None
    assert kept_issue.dismissed_version
