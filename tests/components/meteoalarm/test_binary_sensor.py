"""Tests for the MeteoAlarm binary sensor platform."""

from typing import Any
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from meteoalarmapi import ServerError, UnexpectedError, WrongCountry
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.meteoalarm.const import CONF_PROVINCE, DOMAIN
from homeassistant.components.meteoalarm.coordinator import SCAN_INTERVAL
from homeassistant.const import (
    CONF_COUNTRY,
    CONF_ENTITY_NAMESPACE,
    CONF_LANGUAGE,
    CONF_NAME,
    CONF_PLATFORM,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.setup import async_setup_component

from .conftest import ALERT

ENTITY_ID = "binary_sensor.test_province"

YAML_CONFIG = {
    BINARY_SENSOR_DOMAIN: {
        CONF_PLATFORM: DOMAIN,
        CONF_COUNTRY: "Netherlands",
        CONF_PROVINCE: "Test province",
        CONF_LANGUAGE: "en-GB",
        CONF_NAME: "Test alert",
    }
}

pytestmark = pytest.mark.freeze_time("2026-01-01T12:00:00+00:00")


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_active_alert(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_meteoalert: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the sensor is on and exposes the alert while it has not expired."""
    await _setup(hass, mock_config_entry)

    mock_meteoalert.assert_called_once_with("netherlands", "Test province", "en-GB")
    assert hass.states.get(ENTITY_ID) == snapshot
    assert entity_registry.async_get(ENTITY_ID).unique_id == (
        mock_config_entry.entry_id
    )


@pytest.mark.parametrize(
    "alert",
    [
        pytest.param({}, id="no_alert"),
        pytest.param(
            ALERT | {"expires": "2026-01-01T11:59:59+00:00"}, id="expired_alert"
        ),
        pytest.param(ALERT | {"expires": "not a date"}, id="invalid_expires"),
    ],
)
async def test_no_active_alert(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meteoalert: MagicMock,
    snapshot: SnapshotAssertion,
    alert: dict[str, Any],
) -> None:
    """Test the sensor is off, without alert attributes, if no alert is valid."""
    mock_meteoalert.return_value.get_alert.return_value = alert

    await _setup(hass, mock_config_entry)

    assert hass.states.get(ENTITY_ID) == snapshot


async def test_alert_without_expires(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meteoalert: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an alert without an expiration time is active until the feed drops it."""
    alert = dict(ALERT)
    del alert["expires"]
    mock_meteoalert.return_value.get_alert.return_value = alert

    await _setup(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON
    assert state.attributes["event"] == ALERT["event"]
    assert "expires" not in state.attributes

    mock_meteoalert.return_value.get_alert.return_value = {}
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(ENTITY_ID).state == STATE_OFF


async def test_alert_expires(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meteoalert: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the sensor turns off once the alert in the feed has expired."""
    await _setup(hass, mock_config_entry)

    assert hass.states.get(ENTITY_ID).state == STATE_ON

    # The feed keeps returning the same alert after it has expired at 18:00.
    freezer.move_to("2026-01-01T18:00:01+00:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_OFF
    assert "event" not in state.attributes


async def test_alert_withdrawn(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meteoalert: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the sensor turns off when the alert is no longer in the feed."""
    await _setup(hass, mock_config_entry)

    assert hass.states.get(ENTITY_ID).state == STATE_ON

    mock_meteoalert.return_value.get_alert.return_value = {}
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_OFF
    assert "event" not in state.attributes


@pytest.mark.parametrize(
    "exception",
    [ServerError("500"), WrongCountry("no feed"), UnexpectedError("timeout")],
)
async def test_unavailable_when_update_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meteoalert: MagicMock,
    freezer: FrozenDateTimeFactory,
    exception: Exception,
) -> None:
    """Test the sensor becomes unavailable when MeteoAlarm can't be reached."""
    await _setup(hass, mock_config_entry)

    assert hass.states.get(ENTITY_ID).state == STATE_ON

    mock_meteoalert.return_value.get_alert.side_effect = exception
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE


async def test_yaml_import(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_meteoalert: MagicMock,
) -> None:
    """Test YAML is imported, keeps its entity ID, and raises a deprecation issue."""
    assert await async_setup_component(hass, BINARY_SENSOR_DOMAIN, YAML_CONFIG)
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].title == "Test alert"
    assert hass.states.get("binary_sensor.test_alert").state == STATE_ON
    assert issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )


async def test_yaml_import_defaults(
    hass: HomeAssistant, mock_meteoalert: MagicMock
) -> None:
    """Test the YAML defaults: the name keeps binary_sensor.meteoalarm, and en."""
    config = {
        BINARY_SENSOR_DOMAIN: {
            CONF_PLATFORM: DOMAIN,
            CONF_COUNTRY: "netherlands",
            CONF_PROVINCE: "Test province",
        }
    }

    assert await async_setup_component(hass, BINARY_SENSOR_DOMAIN, config)
    await hass.async_block_till_done()

    mock_meteoalert.assert_called_with("netherlands", "Test province", "en")
    assert hass.states.get("binary_sensor.meteoalarm") is not None


async def test_yaml_import_already_imported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_config_entry: MockConfigEntry,
    mock_meteoalert: MagicMock,
) -> None:
    """Test YAML that was imported before only raises the deprecation issue."""
    mock_config_entry.add_to_hass(hass)

    assert await async_setup_component(hass, BINARY_SENSOR_DOMAIN, YAML_CONFIG)
    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )


@pytest.mark.parametrize(
    ("side_effect", "reason"),
    [
        (WrongCountry("no feed"), "invalid_country"),
        (ServerError("500"), "cannot_connect"),
    ],
)
async def test_yaml_import_failed(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_meteoalert: MagicMock,
    side_effect: Exception,
    reason: str,
) -> None:
    """Test each failed import raises its own issue saying why, and no entry."""
    mock_meteoalert.return_value.get_alert.side_effect = side_effect
    config = {
        BINARY_SENSOR_DOMAIN: [
            YAML_CONFIG[BINARY_SENSOR_DOMAIN],
            YAML_CONFIG[BINARY_SENSOR_DOMAIN] | {CONF_PROVINCE: "Other province"},
        ]
    }

    assert await async_setup_component(hass, BINARY_SENSOR_DOMAIN, config)
    await hass.async_block_till_done()

    assert not hass.config_entries.async_entries(DOMAIN)
    assert hass.states.get("binary_sensor.test_alert") is None
    for region in (
        "netherlands_test_province_en_gb",
        "netherlands_other_province_en_gb",
    ):
        assert issue_registry.async_get_issue(
            DOMAIN, f"deprecated_yaml_import_issue_{reason}_{region}"
        )
    assert not issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )


async def test_yaml_import_entity_namespace(
    hass: HomeAssistant, mock_meteoalert: MagicMock
) -> None:
    """Test the imported entity keeps the entity ID the YAML namespace gave it."""
    config = {
        BINARY_SENSOR_DOMAIN: YAML_CONFIG[BINARY_SENSOR_DOMAIN]
        | {CONF_ENTITY_NAMESPACE: "local"}
    }

    assert await async_setup_component(hass, BINARY_SENSOR_DOMAIN, config)
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.local_test_alert").state == STATE_ON


async def test_yaml_import_same_region_twice(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_meteoalert: MagicMock,
) -> None:
    """Test a region in YAML twice is imported once, without an import issue."""
    config = {
        BINARY_SENSOR_DOMAIN: [
            YAML_CONFIG[BINARY_SENSOR_DOMAIN],
            YAML_CONFIG[BINARY_SENSOR_DOMAIN],
        ]
    }

    assert await async_setup_component(hass, BINARY_SENSOR_DOMAIN, config)
    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert not [
        issue for issue in issue_registry.issues.values() if issue.domain == DOMAIN
    ]
    assert issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )
