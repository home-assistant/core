"""Tests for the Bitcoin sensor platform."""

from unittest.mock import MagicMock

from blockchain.exchangerates import Currency
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.bitcoin.const import DOMAIN
from homeassistant.components.bitcoin.sensor import SCAN_INTERVAL
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_CURRENCY,
    CONF_DISPLAY_OPTIONS,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.setup import async_setup_component

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

ENTITY_EXCHANGE_RATE = "sensor.exchange_rate_1_btc"

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
async def test_no_entities_when_api_unreachable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_statistics: MagicMock,
) -> None:
    """Test the platform setup is retried when blockchain.com cannot be reached."""
    mock_statistics.side_effect = OSError("boom")

    await setup_integration(hass, mock_config_entry)

    assert not hass.states.async_all(SENSOR_DOMAIN)


@pytest.mark.usefixtures("mock_statistics")
async def test_falls_back_to_usd_when_currency_not_quoted(
    hass: HomeAssistant,
    mock_exchangerates: MagicMock,
) -> None:
    """Test the exchange rate falls back to USD when the currency is gone."""
    mock_exchangerates.return_value = {
        "USD": Currency(79618.09, 79622.5, 79613.7, "$", 79600.7)
    }
    entry = MockConfigEntry(domain=DOMAIN, title="Bitcoin", data={CONF_CURRENCY: "EUR"})

    await setup_integration(hass, entry)

    state = hass.states.get(ENTITY_EXCHANGE_RATE)
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == "USD"


@pytest.mark.usefixtures("mock_exchangerates")
async def test_one_fetch_per_cycle(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_statistics: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the sensors share a single fetch instead of polling one by one."""
    await setup_integration(hass, mock_config_entry)
    assert mock_statistics.call_count == 1

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_statistics.call_count == 2


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

    assert await async_setup_component(
        hass,
        SENSOR_DOMAIN,
        {SENSOR_DOMAIN: {**YAML_CONFIG[SENSOR_DOMAIN], CONF_CURRENCY: "USD"}},
    )
    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )


@pytest.mark.usefixtures("mock_statistics", "mock_exchangerates")
async def test_yaml_import_other_currency_dropped(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test YAML asking for another currency than the entry is reported."""
    mock_config_entry.add_to_hass(hass)

    assert await async_setup_component(hass, SENSOR_DOMAIN, YAML_CONFIG)
    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert issue_registry.async_get_issue(
        DOMAIN, "deprecated_yaml_import_issue_dropped_currency_EUR"
    )
    assert not issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )


@pytest.mark.usefixtures("mock_statistics", "mock_exchangerates")
async def test_yaml_import_second_currency_dropped(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test a second platform block asking for another currency is reported."""
    assert await async_setup_component(
        hass,
        SENSOR_DOMAIN,
        {
            SENSOR_DOMAIN: [
                YAML_CONFIG[SENSOR_DOMAIN],
                {**YAML_CONFIG[SENSOR_DOMAIN], CONF_CURRENCY: "USD"},
            ]
        },
    )
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    dropped = "USD" if entries[0].data[CONF_CURRENCY] == "EUR" else "EUR"
    assert issue_registry.async_get_issue(
        DOMAIN, f"deprecated_yaml_import_issue_dropped_currency_{dropped}"
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
