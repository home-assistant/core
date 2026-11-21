"""HTTP parity, metadata, options, identity warnings and statistics compatibility."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from iammeter.async_client import IammeterAuthError
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant.components.iammeter.const import DOMAIN
from homeassistant.components.iammeter.diagnostics import (
    async_get_config_entry_diagnostics,
)
from homeassistant.components.recorder.models import (
    StatisticMeanType,
    StatisticMetaData,
)
from homeassistant.components.sensor import recorder as sensor_recorder
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import CONF_SCAN_INTERVAL, Platform
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.util import dt as dt_util

from . import MOCK_DATA, MOCK_INPUT

ROW = [230, 2, -460, 100, 10, 50, 0.95]
ENDPOINT = "http://192.0.2.1:80/monitorjson"


@pytest.mark.parametrize(
    ("method", "model", "channels", "count", "readings"),
    [
        ("1-x", "WEM3080", 1, 8, {"Data": ROW[:5]}),
        ("2-x", "WEM3080T", 3, 30, {"Datas": [ROW] * 3}),  # codespell:ignore datas
        ("3-x", "WEM3046T", 3, 30, {"Datas": [ROW] * 3}),  # codespell:ignore datas
        ("4-x", "WEM3050T", 3, 30, {"Datas": [ROW] * 3}),  # codespell:ignore datas
        ("5-x", "WEM2067", 2, 20, {"Datas": [ROW] * 2}),  # codespell:ignore datas
        ("6-x", "WEM3063T", 3, 30, {"Datas": [ROW] * 3}),  # codespell:ignore datas
        ("legacy", "WEM3162", 1, 8, {"data": ROW[:5]}),
    ],
)
async def test_all_models_and_metadata(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    method: str,
    model: str,
    channels: int,
    count: int,
    readings: dict[str, list[float] | list[list[float]]],
) -> None:
    """Recognize seven models, provide metadata, and enable every returned field."""
    payload = {
        "SN": "test-meter",
        "method": method,
        "version": "i.test",
        "mac": "00:00:00:00:00:01",
        "EA": {"Reactive": [[10, 20, 30]] * channels},
    }
    payload.update(readings)
    aioclient_mock.get(ENDPOINT, json=payload)
    flow = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(flow["flow_id"], MOCK_INPUT)
    await hass.async_block_till_done()
    entry = result["result"]
    assert entry.state is ConfigEntryState.LOADED
    assert entry.title == f"IAMMETER {model} test-meter"
    entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    assert len(entities) == count
    assert all(entity.disabled_by is None for entity in entities)
    assert (
        len(
            {
                hass.states.get(entity.entity_id).attributes["friendly_name"]
                for entity in entities
            }
        )
        == count
    )
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "test-meter"), entry.entry_id
    )
    assert device.manufacturer == "IAMMETER"
    assert device.model == model
    assert device.serial_number == "test-meter"
    assert device.sw_version == "i.test"
    assert device.configuration_url == "http://192.0.2.1/"


@pytest.mark.parametrize(
    ("method", "count"), [("2-x", 3), ("3-x", 3), ("4-x", 3), ("5-x", 2), ("6-x", 3)]
)
async def test_dynamic_net_and_reactive(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    aioclient_mock: AiohttpClientMocker,
    entity_registry: er.EntityRegistry,
    method: str,
    count: int,
) -> None:
    """Discover optional fields once and recover them without zeroing or duplicates."""
    payload = {
        "method": method,
        "SN": "test-meter",
        "Datas": [ROW] * count,  # codespell:ignore datas
    }
    aioclient_mock.get(ENDPOINT, json=payload)
    entry = MockConfigEntry(
        domain=DOMAIN, title="Meter", unique_id="test-meter", data=MOCK_INPUT
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    aioclient_mock.clear_requests()
    aioclient_mock.get(
        ENDPOINT,
        json={
            **payload,
            "Datas": [ROW] * (count + 1),  # codespell:ignore datas
            "EA": {"Reactive": [[10, 20, 30]] * count},
        },
    )
    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    power = entity_registry.async_get_entity_id(
        Platform.SENSOR, DOMAIN, "test-meter_Power_Net"
    )
    reactive = entity_registry.async_get_entity_id(
        Platform.SENSOR, DOMAIN, "test-meter_ReactivePower_A"
    )
    assert hass.states.get(power).state == "-460"
    assert hass.states.get(reactive).state == "10"
    total = len(er.async_entries_for_config_entry(entity_registry, entry.entry_id))
    aioclient_mock.clear_requests()
    aioclient_mock.get(ENDPOINT, json=payload)
    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert hass.states.get(power).state == "unavailable"
    assert hass.states.get(reactive).state == "unavailable"
    aioclient_mock.clear_requests()
    aioclient_mock.get(
        ENDPOINT,
        json={
            **payload,
            "Datas": [ROW] * (count + 1),  # codespell:ignore datas
            "EA": {"Reactive": [[10, 20, 30]] * count},
        },
    )
    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert hass.states.get(power).state == "-460"
    assert hass.states.get(reactive).state == "10"
    assert (
        len(er.async_entries_for_config_entry(entity_registry, entry.entry_id)) == total
    )


async def test_changed_identity_does_not_block(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_meter: MagicMock,
    mock_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Continue polling like HACS, but explicitly warn about mixed history."""
    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()
    power = entity_registry.async_get_entity_id(
        Platform.SENSOR, DOMAIN, "test-meter_Power"
    )
    mock_meter.return_value.async_get_data.return_value = {
        **MOCK_DATA,
        "sn": "replacement",
        "Power": 690,
    }
    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    assert hass.states.get(power).state == "690"
    assert issue_registry.async_get_issue(
        DOMAIN, f"identity_changed_{mock_entry.entry_id}"
    )
    await hass.config_entries.async_reload(mock_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(power).state == "690"
    assert (
        len(er.async_entries_for_config_entry(entity_registry, mock_entry.entry_id))
        == 5
    )
    mock_meter.return_value.async_get_data.return_value = MOCK_DATA
    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert not issue_registry.async_get_issue(
        DOMAIN, f"identity_changed_{mock_entry.entry_id}"
    )


@pytest.mark.usefixtures("mock_setup_entry", "mock_meter")
async def test_fixed_polling_form(hass: HomeAssistant) -> None:
    """Keep polling fixed as required by the Core appropriate-polling rule."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert CONF_SCAN_INTERVAL not in {
        key.schema for key in result["data_schema"].schema
    }


@pytest.mark.usefixtures("mock_setup_entry", "mock_meter")
async def test_reauthentication(
    hass: HomeAssistant, mock_entry: MockConfigEntry
) -> None:
    """Validate the same meter before accepting updated credentials."""
    mock_entry.add_to_hass(hass)
    await mock_entry.start_reauth_flow(hass)
    await hass.async_block_till_done()
    result = hass.config_entries.flow.async_progress()[0]
    assert result["step_id"] == "reauth_confirm"
    with patch.object(hass.config_entries, "async_reload", new_callable=AsyncMock):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {**MOCK_INPUT, "username": "custom", "password": "secret"},
        )
        await hass.async_block_till_done()
    assert result["reason"] == "reauth_successful"
    assert mock_entry.data["username"] == "custom"
    assert mock_entry.data["password"] == "secret"


@pytest.mark.usefixtures("mock_setup_entry", "mock_meter")
async def test_password_without_username(hass: HomeAssistant) -> None:
    """Reject incomplete credentials before opening the connection."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**MOCK_INPUT, "password": "secret"}
    )
    assert result["errors"] == {"base": "invalid_auth"}


async def test_auth_failure_starts_reauth(
    hass: HomeAssistant, mock_meter: MagicMock, mock_entry: MockConfigEntry
) -> None:
    """Authentication failures are distinguishable from offline devices."""
    mock_meter.return_value.async_get_data.side_effect = IammeterAuthError()
    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_entry.state is ConfigEntryState.SETUP_ERROR
    assert mock_entry.entry_id in {
        flow["context"]["entry_id"]
        for flow in hass.config_entries.flow.async_progress()
    }


async def test_redacted_diagnostics(
    hass: HomeAssistant, mock_meter: MagicMock, mock_entry: MockConfigEntry
) -> None:
    """Never disclose local addresses, credentials, serials or MACs."""
    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()
    data = await async_get_config_entry_diagnostics(hass, mock_entry)
    assert data["entry"]["data"]["host"] == "**REDACTED**"
    assert data["entry"]["unique_id"] == "**REDACTED**"
    assert data["measurement"]["sn"] == "**REDACTED**"
    assert data["measurement"]["mac"] == "**REDACTED**"
    assert data["measurement"]["Power"] == 460


@pytest.mark.parametrize("old_unit_class", [None, "unitless"])
def test_pf_statistics_unit_transition(
    hass: HomeAssistant, old_unit_class: str | None
) -> None:
    """The recorder converts new ratio values into existing percent statistics."""
    metadata: StatisticMetaData = {
        "source": DOMAIN,
        "statistic_id": "sensor.old_pf",
        "name": None,
        "unit_of_measurement": "%",
        "unit_class": old_unit_class,
        "mean_type": StatisticMeanType.ARITHMETIC,
        "has_sum": False,
    }
    old = State(
        "sensor.old_pf",
        "95",
        {"device_class": "power_factor", "unit_of_measurement": "%"},
    )
    new = State("sensor.old_pf", ".95", {"device_class": "power_factor"})
    unit_class, unit, values = sensor_recorder._normalize_states(
        hass,
        {"sensor.old_pf": (1, metadata)},
        [(95, old), (0.95, new)],
        "sensor.old_pf",
        None,
    )
    assert unit_class == "unitless"
    assert unit == "%"
    assert [value for value, _ in values] == [95, 95]


@pytest.mark.usefixtures("mock_setup_entry")
async def test_legacy_mac_identity(hass: HomeAssistant, mock_meter: MagicMock) -> None:
    """An old WEM3162 can use its MAC, never its IP, as stable identity."""
    mock_meter.return_value.async_get_data.return_value = {
        **MOCK_DATA,
        "Model": "WEM3162",
        "sn": None,
    }
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], MOCK_INPUT
    )
    assert result["result"].unique_id == "mac_000000000001"


async def test_registered_net_keeps_a_name_when_absent(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    entity_registry: er.EntityRegistry,
) -> None:
    """Restore a historical NET entity with its name even when NET is absent."""
    entry = MockConfigEntry(
        domain=DOMAIN, title="Meter", unique_id="test-meter", data=MOCK_INPUT
    )
    entry.add_to_hass(hass)
    old = entity_registry.async_get_or_create(
        Platform.SENSOR,
        DOMAIN,
        "test-meter_Power_Net",
        config_entry=entry,
        suggested_object_id="original_net",
    )
    aioclient_mock.get(
        ENDPOINT,
        json={
            "method": "2-x",
            "SN": "test-meter",
            "Datas": [ROW] * 3,  # codespell:ignore datas
        },
    )
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    state = hass.states.get(old.entity_id)
    assert state.state == "unavailable"
    assert state.attributes["friendly_name"] == "Meter Net power"


@pytest.mark.parametrize(
    "mac", ["::::", "not-a-mac", "000000000000", "ff:ff:ff:ff:ff:ff", 42, None]
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_invalid_legacy_mac_identity(
    hass: HomeAssistant, mock_meter: MagicMock, mac: str | int | None
) -> None:
    """An invalid MAC must not become a shared identity for older meters."""
    mock_meter.return_value.async_get_data.return_value = {
        **MOCK_DATA,
        "Model": "WEM3162",
        "sn": None,
        "mac": mac,
    }
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], MOCK_INPUT
    )
    assert result["errors"] == {"base": "invalid_data"}


@pytest.mark.parametrize("mac", ["AA:BB:CC:DD:EE:FF", "aa-bb-cc-dd-ee-ff"])
@pytest.mark.usefixtures("mock_setup_entry")
async def test_canonical_legacy_mac_identity(
    hass: HomeAssistant, mock_meter: MagicMock, mac: str
) -> None:
    """Common MAC notations identify the same older device."""
    mock_meter.return_value.async_get_data.return_value = {
        **MOCK_DATA,
        "Model": "WEM3162",
        "sn": None,
        "mac": mac,
    }
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], MOCK_INPUT
    )
    assert result["result"].unique_id == "mac_aabbccddeeff"
