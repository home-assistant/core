"""Test the Teslemetry energy live/info/tariff stream wiring."""

from copy import deepcopy
from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.teslemetry.coordinator import ENERGY_HISTORY_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_platform
from .const import LIVE_STATUS, METADATA_ENERGY, PRODUCTS_ENERGY, SITE_INFO

from tests.common import async_fire_time_changed

SITE_ID = "123456"
OTHER_SITE_ID = "98765"

TARIFF_V2 = SITE_INFO["response"]["tariff_content_v2"]
SLIM_SITE_INFO = {
    key: value
    for key, value in SITE_INFO["response"].items()
    if key != "tariff_content_v2"
}


def _live_status(**overrides: object) -> dict:
    """Return a copy of the live_status document with overrides applied."""
    data = deepcopy(LIVE_STATUS["response"])
    data.update(overrides)
    return data


@pytest.fixture
def mock_energy_only(mock_products: AsyncMock, mock_metadata: MagicMock) -> None:
    """Patch products and metadata to an energy-only account."""
    mock_products.return_value = PRODUCTS_ENERGY
    mock_metadata.return_value = METADATA_ENERGY


@pytest.mark.usefixtures("mock_energy_only")
async def test_energy_only_creates_stream_and_listeners(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_add_listener: MagicMock,
    mock_stream_listen: AsyncMock,
) -> None:
    """An energy-only account opens one stream and still creates credit sensors."""
    entry = await setup_platform(hass, [Platform.SENSOR])
    assert entry.state is ConfigEntryState.LOADED

    # Exactly one account-wide stream is created and started.
    assert entry.runtime_data.stream is not None
    mock_stream_listen.assert_called_once()

    # The site's live_status listener is registered and drives the coordinator.
    mock_add_listener.send(
        {"site_id": SITE_ID, "live_status": _live_status(solar_power=999)}
    )
    await hass.async_block_till_done()
    state = hass.states.get("sensor.energy_site_solar_power")
    assert state is not None
    assert state.state == "0.999"

    # Credit sensors are still created for an energy-only account.
    assert entry.unique_id is not None
    assert entity_registry.async_get_entity_id(
        Platform.SENSOR, "teslemetry", f"{entry.unique_id}_credit_quota"
    )


async def test_stream_topics_allowlist(hass: HomeAssistant) -> None:
    """The stream subscribes to exactly the topics the integration consumes."""
    entry = await setup_platform(hass, [Platform.SENSOR])

    assert entry.runtime_data.stream is not None
    assert entry.runtime_data.stream.topics == [
        "state",
        "vehicle_data",
        "data",
        "connectivity",
        "credits",
        "live_status",
        "site_info",
        "tariff_content_v2",
    ]


@pytest.mark.parametrize(
    "extra_event_fields",
    [
        pytest.param({}, id="live"),
        pytest.param({"isCache": True}, id="cache"),
    ],
)
async def test_live_status_stream_updates(
    hass: HomeAssistant,
    mock_add_listener: MagicMock,
    extra_event_fields: dict[str, object],
) -> None:
    """Live and snapshot live_status events drive the same entity states."""
    await setup_platform(hass, [Platform.SENSOR])

    # The REST cold read populated the fixture value.
    assert hass.states.get("sensor.energy_site_solar_power").state == "1.185"
    assert hass.states.get("sensor.wall_connector_power").state == "0.0"

    event = {
        "site_id": SITE_ID,
        "live_status": _live_status(solar_power=456),
        **extra_event_fields,
    }
    event["live_status"]["wall_connectors"][0]["wall_connector_power"] = 789
    mock_add_listener.send(event)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.energy_site_solar_power").state == "0.456"
    assert hass.states.get("sensor.wall_connector_power").state == "0.789"


@pytest.mark.parametrize(
    "order",
    [
        pytest.param(("site_info", "tariff"), id="site_info_first"),
        pytest.param(("tariff", "site_info"), id="tariff_first"),
    ],
)
async def test_site_info_and_tariff_compose(
    hass: HomeAssistant,
    mock_add_listener: MagicMock,
    order: tuple[str, str],
) -> None:
    """Slim site_info and tariff events are independently replaceable partitions."""
    entry = await setup_platform(hass, [Platform.CALENDAR])
    info_coordinator = entry.runtime_data.energysites[0].info_coordinator

    # The REST cold read populated the tariff code with the fixture value.
    assert info_coordinator.data["tariff_content_v2_code"] == "Test"

    slim = deepcopy(SLIM_SITE_INFO)
    slim["version"] = "99.9.9"
    # A distinct tariff code proves the streamed tariff replaces the cold read.
    streamed_tariff = deepcopy(TARIFF_V2)
    streamed_tariff["code"] = "Streamed"
    events = {
        "site_info": {"site_id": SITE_ID, "site_info": slim},
        "tariff": {"site_id": SITE_ID, "tariff_content_v2": streamed_tariff},
    }

    for name in order:
        mock_add_listener.send(events[name])
        await hass.async_block_till_done()

    # Both partitions survive regardless of arrival order.
    assert info_coordinator.data["version"] == "99.9.9"
    assert info_coordinator.data["tariff_content_v2_code"] == "Streamed"
    assert info_coordinator.data["tariff_content_v2_seasons"]
    assert hass.states.get("calendar.energy_site_buy_tariff").state != STATE_UNAVAILABLE


async def test_tariff_removal_clears_flattened_keys(
    hass: HomeAssistant,
    mock_add_listener: MagicMock,
) -> None:
    """A tariff_content_v2 removal clears flattened keys and calendars."""
    entry = await setup_platform(hass, [Platform.CALENDAR])
    info_coordinator = entry.runtime_data.energysites[0].info_coordinator

    assert "tariff_content_v2_seasons" in info_coordinator.data
    assert hass.states.get("calendar.energy_site_buy_tariff").state != STATE_UNAVAILABLE

    mock_add_listener.send({"site_id": SITE_ID, "tariff_content_v2": None})
    await hass.async_block_till_done()

    assert "tariff_content_v2_seasons" not in info_coordinator.data
    assert hass.states.get("calendar.energy_site_buy_tariff").state == STATE_UNAVAILABLE


async def test_slim_site_info_replacement_drops_removed_field(
    hass: HomeAssistant,
    mock_add_listener: MagicMock,
) -> None:
    """A removed field in a replacement site_info event does not linger."""
    entry = await setup_platform(hass, [Platform.CALENDAR])
    info_coordinator = entry.runtime_data.energysites[0].info_coordinator

    assert "nameplate_power" in info_coordinator.data

    slim = deepcopy(SLIM_SITE_INFO)
    slim.pop("nameplate_power")
    mock_add_listener.send({"site_id": SITE_ID, "site_info": slim})
    await hass.async_block_till_done()

    assert "nameplate_power" not in info_coordinator.data
    # The tariff partition is untouched by a site_info replacement.
    assert "tariff_content_v2_seasons" in info_coordinator.data


async def test_other_site_events_ignored(
    hass: HomeAssistant,
    mock_add_listener: MagicMock,
) -> None:
    """Events for a different site do not update the target site."""
    await setup_platform(hass, [Platform.SENSOR])
    assert hass.states.get("sensor.energy_site_solar_power").state == "1.185"

    mock_add_listener.send(
        {"site_id": OTHER_SITE_ID, "live_status": _live_status(solar_power=1)}
    )
    await hass.async_block_till_done()

    assert hass.states.get("sensor.energy_site_solar_power").state == "1.185"


async def test_no_recurring_rest_polling(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_live_status: AsyncMock,
    mock_site_info: AsyncMock,
) -> None:
    """The live/info REST cold reads happen once and do not recur."""
    await setup_platform(hass, [Platform.SENSOR])
    assert mock_live_status.call_count == 1
    assert mock_site_info.call_count == 1

    # Advancing well past the old 30-second poll intervals triggers no REST reads.
    freezer.tick(ENERGY_HISTORY_INTERVAL * 2)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_live_status.call_count == 1
    assert mock_site_info.call_count == 1


async def test_stream_disconnect_marks_unavailable_and_recovers(
    hass: HomeAssistant,
    mock_add_listener: MagicMock,
    mock_add_connection_listener: MagicMock,
) -> None:
    """A dropped stream marks energy entities unavailable until documents resume."""
    await setup_platform(hass, [Platform.SENSOR, Platform.CALENDAR])

    # Both stream-driven coordinators start available from the setup cold read.
    assert hass.states.get("sensor.energy_site_solar_power").state == "1.185"
    assert hass.states.get("calendar.energy_site_buy_tariff").state != STATE_UNAVAILABLE

    # A stream disconnect fails the live and info/tariff coordinators.
    mock_add_connection_listener.send(False)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.energy_site_solar_power").state == STATE_UNAVAILABLE
    assert hass.states.get("calendar.energy_site_buy_tariff").state == STATE_UNAVAILABLE

    # A streamed live_status document restores the live coordinator on reconnect.
    mock_add_listener.send(
        {"site_id": SITE_ID, "live_status": _live_status(solar_power=456)}
    )
    await hass.async_block_till_done()
    assert hass.states.get("sensor.energy_site_solar_power").state == "0.456"

    # A streamed site_info document restores the info/tariff coordinator.
    mock_add_listener.send({"site_id": SITE_ID, "site_info": deepcopy(SLIM_SITE_INFO)})
    await hass.async_block_till_done()
    assert hass.states.get("calendar.energy_site_buy_tariff").state != STATE_UNAVAILABLE


async def test_unload_unsubscribes_and_closes_stream(
    hass: HomeAssistant,
) -> None:
    """Unload runs each listener unsubscribe and closes the shared stream."""
    live_unsub = MagicMock()
    info_unsub = MagicMock()
    tariff_unsub = MagicMock()

    with (
        patch(
            "teslemetry_stream.TeslemetryStreamEnergySite.listen_LiveStatus",
            return_value=live_unsub,
        ),
        patch(
            "teslemetry_stream.TeslemetryStreamEnergySite.listen_SiteInfo",
            return_value=info_unsub,
        ),
        patch(
            "teslemetry_stream.TeslemetryStreamEnergySite.listen_TariffContentV2",
            return_value=tariff_unsub,
        ),
        patch("teslemetry_stream.TeslemetryStream.close") as mock_close,
    ):
        entry = await setup_platform(hass, [Platform.SENSOR])
        assert entry.state is ConfigEntryState.LOADED

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

    live_unsub.assert_called_once()
    info_unsub.assert_called_once()
    tariff_unsub.assert_called_once()
    mock_close.assert_called_once()
