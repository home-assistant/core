"""Tests for the Bitcoin sensor platform."""

from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.bitcoin.const import DOMAIN, SCAN_INTERVAL
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import CONF_CURRENCY, CONF_DISPLAY_OPTIONS, STATE_UNAVAILABLE
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.setup import async_setup_component

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

ENTITY_EXCHANGE_RATE = "sensor.bitcoin_exchange_rate"

YAML_CONFIG = {
    SENSOR_DOMAIN: {
        "platform": DOMAIN,
        CONF_DISPLAY_OPTIONS: ["exchangerate"],
        CONF_CURRENCY: "EUR",
    }
}


@pytest.mark.usefixtures("mock_statistics", "mock_exchangerates")
async def test_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the sensor entities and their states."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("mock_exchangerates")
async def test_entities_unavailable_on_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_statistics: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the sensors go unavailable when blockchain.com cannot be reached."""
    await setup_integration(hass, mock_config_entry)
    mock_statistics.side_effect = OSError("boom")

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(ENTITY_EXCHANGE_RATE).state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("mock_statistics", "mock_exchangerates")
async def test_yaml_import(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test the YAML platform is imported and reported as deprecated."""
    assert await async_setup_component(hass, SENSOR_DOMAIN, YAML_CONFIG)
    await hass.async_block_till_done()

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.data == {CONF_CURRENCY: "EUR"}
    assert issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )


@pytest.mark.usefixtures("mock_statistics", "mock_exchangerates")
async def test_yaml_import_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test no second entry is created once one exists, but the issue still is."""
    mock_config_entry.add_to_hass(hass)

    assert await async_setup_component(hass, SENSOR_DOMAIN, YAML_CONFIG)
    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )


@pytest.mark.parametrize(
    ("currency", "side_effect", "reason"),
    [
        pytest.param("EUR", OSError("boom"), "cannot_connect", id="cannot_connect"),
        pytest.param("XYZ", None, "unknown_currency", id="unknown_currency"),
    ],
)
async def test_yaml_import_failure(
    hass: HomeAssistant,
    mock_exchangerates: MagicMock,
    issue_registry: ir.IssueRegistry,
    currency: str,
    side_effect: Exception | None,
    reason: str,
) -> None:
    """Test a failed YAML import raises a repair issue explaining why."""
    mock_exchangerates.side_effect = side_effect

    assert await async_setup_component(
        hass,
        SENSOR_DOMAIN,
        {SENSOR_DOMAIN: {**YAML_CONFIG[SENSOR_DOMAIN], CONF_CURRENCY: currency}},
    )
    await hass.async_block_till_done()

    assert not hass.config_entries.async_entries(DOMAIN)
    assert issue_registry.async_get_issue(
        DOMAIN, f"deprecated_yaml_import_issue_{reason}"
    )
