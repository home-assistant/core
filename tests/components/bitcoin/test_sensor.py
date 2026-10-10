"""Tests for the Bitcoin sensor platform."""

from unittest.mock import MagicMock

from blockchain.exchangerates import Currency
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.bitcoin.const import DOMAIN
from homeassistant.components.bitcoin.sensor import (
    COLLIDING_OPTIONS,
    SCAN_INTERVAL,
    SENSOR_TYPES,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import SOURCE_IGNORE
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_CURRENCY,
    CONF_DISPLAY_OPTIONS,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed

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
    snapshot: SnapshotAssertion,
) -> None:
    """Test the sensor entities and their states."""
    await setup_integration(hass, mock_config_entry)

    states = hass.states.async_all(SENSOR_DOMAIN)
    assert len(states) == 21
    for state in sorted(states, key=lambda state: state.entity_id):
        assert state == snapshot(name=state.entity_id)


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
    # The interval poll runs as a background task, so waiting for it is needed.
    await hass.async_block_till_done(wait_background_tasks=True)

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
        DOMAIN, "deprecated_yaml_import_issue_dropped_currency_eur"
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
        DOMAIN, f"deprecated_yaml_import_issue_dropped_currency_{dropped.lower()}"
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
        DOMAIN, f"deprecated_yaml_import_issue_{reason}_{currency.lower()}"
    )


@pytest.mark.parametrize(
    ("display_options", "expected_issue"),
    [
        pytest.param(
            ["trade_volume_usd"], "reused_entity_id_trade_volume", id="trade_volume_usd"
        ),
        pytest.param(
            ["miners_revenue_btc"],
            "reused_entity_id_miners_revenue",
            id="miners_revenue_btc",
        ),
        pytest.param(["trade_volume_btc"], None, id="trade_volume_btc_keeps_its_id"),
        pytest.param(
            ["trade_volume_btc", "trade_volume_usd"], None, id="both_keep_their_ids"
        ),
        pytest.param(["exchangerate"], None, id="unaffected_option"),
    ],
)
@pytest.mark.usefixtures("mock_statistics", "mock_exchangerates")
async def test_yaml_import_warns_about_reused_entity_ids(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    display_options: list[str],
    expected_issue: str | None,
) -> None:
    """Test only the users whose entity ID changed meaning are warned."""
    assert await async_setup_component(
        hass,
        SENSOR_DOMAIN,
        {
            SENSOR_DOMAIN: {
                **YAML_CONFIG[SENSOR_DOMAIN],
                CONF_DISPLAY_OPTIONS: display_options,
            }
        },
    )
    await hass.async_block_till_done()

    reused = [i for i in issue_registry.issues.values() if "reused" in i.issue_id]
    assert [i.issue_id for i in reused] == ([expected_issue] if expected_issue else [])


@pytest.mark.usefixtures("mock_statistics", "mock_exchangerates")
async def test_yaml_import_with_ignored_entry(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test an ignored entry does not break the import."""
    MockConfigEntry(
        domain=DOMAIN, source=SOURCE_IGNORE, data={}, title="Bitcoin"
    ).add_to_hass(hass)

    assert await async_setup_component(hass, SENSOR_DOMAIN, YAML_CONFIG)
    await hass.async_block_till_done()

    assert issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}"
    )


@pytest.mark.usefixtures("mock_statistics", "mock_exchangerates")
async def test_colliding_options_match_the_created_entities(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test COLLIDING_OPTIONS still describes the entity IDs that get created."""
    await setup_integration(hass, mock_config_entry)

    units = {
        description.key: description.native_unit_of_measurement
        for description in SENSOR_TYPES
    }
    for option, takes_over, entity_id, moved_to in COLLIDING_OPTIONS:
        takes_it = hass.states.get(f"sensor.{entity_id}")
        moved = hass.states.get(f"sensor.{moved_to}")
        assert takes_it.attributes[ATTR_UNIT_OF_MEASUREMENT] == units[takes_over]
        assert moved.attributes[ATTR_UNIT_OF_MEASUREMENT] == units[option]
