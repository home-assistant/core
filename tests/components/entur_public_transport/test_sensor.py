"""Tests for the Entur public transport sensor platform."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from aiohttp import ClientError
import probatio
import pytest

from homeassistant.components.entur_public_transport.const import (
    DOMAIN,
    PLATFORM_MODE_SELECTED,
    PLATFORM_MODE_STOP_PLACE,
)
from homeassistant.components.entur_public_transport.sensor import (
    PLATFORM_SCHEMA,
    EnturPublicTransportSensor,
    EnturStopConfiguration,
    _async_setup,
    _stop_configurations,
    async_setup_platform,
    due_in_minutes,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady


def test_platform_schema_defaults() -> None:
    """Test the defaults used by the YAML platform configuration."""
    config = PLATFORM_SCHEMA(
        {"platform": "entur_public_transport", "stop_ids": "NSR:StopPlace:1"}
    )

    assert config["stop_ids"] == ["NSR:StopPlace:1"]
    assert config["expand_platforms"] is True
    assert config["name"] == "Entur"
    assert config["show_on_map"] is False
    assert config["line_whitelist"] == []
    assert config["omit_non_boarding"] is True
    assert config["number_of_departures"] == 2


def test_platform_schema_requires_stop_ids() -> None:
    """Test that stop IDs are required by the YAML platform configuration."""
    with pytest.raises(probatio.Invalid):
        PLATFORM_SCHEMA({"platform": "entur_public_transport"})


def test_due_in_minutes() -> None:
    """Test calculating the number of minutes until a departure."""
    now = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)

    with patch(
        "homeassistant.components.entur_public_transport.sensor.dt_util.now",
        return_value=now,
    ):
        assert due_in_minutes(now + timedelta(minutes=6, seconds=59)) == 6


async def test_async_setup_platform_creates_entities(
    hass: HomeAssistant,
) -> None:
    """Test that configured stops and quays become sensors."""
    stop_info = {
        "NSR:StopPlace:1": SimpleNamespace(name="Central station"),
        "NSR:Quay:2": SimpleNamespace(name="Platform 2"),
    }
    api = Mock()
    api.expand_all_quays = AsyncMock()
    api.update = AsyncMock()
    api.all_stop_places_quays.return_value = list(stop_info)
    api.get_stop_info.side_effect = stop_info.__getitem__
    add_entities = Mock()
    client_session = Mock()

    config = PLATFORM_SCHEMA(
        {
            "platform": "entur_public_transport",
            "stop_ids": ["NSR:StopPlace:1", "NSR:Quay:2"],
            "name": "Transport",
            "expand_platforms": True,
            "show_on_map": True,
            "line_whitelist": ["RUT:Line:1"],
            "omit_non_boarding": False,
            "number_of_departures": 4,
        }
    )

    with (
        patch(
            "homeassistant.components.entur_public_transport.sensor.EnturPublicTransportData",
            return_value=api,
        ) as data_class,
        patch(
            "homeassistant.components.entur_public_transport.sensor.async_get_clientsession",
            return_value=client_session,
        ),
    ):
        await async_setup_platform(hass, config, add_entities)

    data_class.assert_called_once()
    client_name = data_class.call_args.args[0]
    assert client_name.startswith("homeassistant-")
    assert data_class.call_args.kwargs == {
        "stops": ["NSR:StopPlace:1"],
        "quays": ["NSR:Quay:2"],
        "line_whitelist": ["RUT:Line:1"],
        "omit_non_boarding": False,
        "number_of_departures": 4,
        "web_session": client_session,
    }
    api.expand_all_quays.assert_awaited_once()
    api.update.assert_awaited_once()

    entities = add_entities.call_args.args[0]
    assert [entity.name for entity in entities] == [
        "Transport Central station",
        "Transport Platform 2",
    ]
    assert [entity.unique_id for entity in entities] == [None, None]
    assert [entity.device_info for entity in entities] == [None, None]
    assert add_entities.call_args.args[1] is True


@pytest.mark.parametrize("method", ["expand_all_quays", "update"])
async def test_async_setup_retries_after_entur_connection_error(
    hass: HomeAssistant,
    method: str,
) -> None:
    """Test temporary Entur errors leave the platform ready to retry."""
    api = Mock()
    api.expand_all_quays = AsyncMock()
    api.update = AsyncMock()
    getattr(api, method).side_effect = ClientError
    add_entities = Mock()
    config = PLATFORM_SCHEMA(
        {"platform": "entur_public_transport", "stop_ids": ["NSR:StopPlace:1"]}
    )

    with (
        patch(
            "homeassistant.components.entur_public_transport.sensor.EnturPublicTransportData",
            return_value=api,
        ),
        pytest.raises(PlatformNotReady),
    ):
        await _async_setup(hass, config, add_entities)

    add_entities.assert_not_called()


def test_subentries_keep_route_filters_per_stop() -> None:
    """Test that each UI stop keeps its own route whitelist."""
    config = PLATFORM_SCHEMA(
        {
            "platform": "entur_public_transport",
            "stop_ids": [],
            "line_whitelist": [],
        }
    )
    subentries = [
        SimpleNamespace(
            subentry_id="stop-1",
            subentry_type="stop_place",
            data={
                "stop_id": "NSR:StopPlace:1",
                "line_whitelist": ["RUT:Line:1"],
            },
        ),
        SimpleNamespace(
            subentry_id="stop-2",
            subentry_type="stop_place",
            data={
                "stop_id": "NSR:StopPlace:2",
                "line_whitelist": ["SKY:Line:2"],
            },
        ),
    ]

    assert _stop_configurations(config, subentries) == [
        EnturStopConfiguration(
            stops=("NSR:StopPlace:1",),
            quays=(),
            line_whitelist=("RUT:Line:1",),
            expand_platforms=True,
            show_on_map=False,
            device_stop_id="NSR:StopPlace:1",
            config_subentry_id="stop-1",
        ),
        EnturStopConfiguration(
            stops=("NSR:StopPlace:2",),
            quays=(),
            line_whitelist=("SKY:Line:2",),
            expand_platforms=True,
            show_on_map=False,
            device_stop_id="NSR:StopPlace:2",
            config_subentry_id="stop-2",
        ),
    ]


def test_legacy_yaml_and_ui_subentries_can_coexist() -> None:
    """Test that existing YAML stops remain independent from UI stops."""
    config = PLATFORM_SCHEMA(
        {
            "platform": "entur_public_transport",
            "stop_ids": ["NSR:StopPlace:legacy"],
            "line_whitelist": ["RUT:Line:legacy"],
        }
    )
    subentries = [
        SimpleNamespace(
            subentry_id="stop-ui",
            subentry_type="stop_place",
            data={
                "stop_id": "NSR:StopPlace:ui",
                "line_whitelist": ["SKY:Line:ui"],
            },
        )
    ]

    assert _stop_configurations(config, subentries) == [
        EnturStopConfiguration(
            stops=("NSR:StopPlace:legacy",),
            quays=(),
            line_whitelist=("RUT:Line:legacy",),
            expand_platforms=True,
            show_on_map=False,
        ),
        EnturStopConfiguration(
            stops=("NSR:StopPlace:ui",),
            quays=(),
            line_whitelist=("SKY:Line:ui",),
            expand_platforms=True,
            show_on_map=False,
            device_stop_id="NSR:StopPlace:ui",
            config_subentry_id="stop-ui",
        ),
    ]


def test_ui_subentry_platform_modes_select_requested_sensors() -> None:
    """Test whole-stop and explicit-platform UI configurations."""
    config = PLATFORM_SCHEMA(
        {
            "platform": "entur_public_transport",
            "stop_ids": [],
            "line_whitelist": [],
        }
    )
    subentries = [
        SimpleNamespace(
            subentry_id="stop-1",
            subentry_type="stop_place",
            data={
                "stop_id": "NSR:StopPlace:1",
                "stop_place_name": "Central station",
                "platform_mode": PLATFORM_MODE_STOP_PLACE,
                "line_whitelist": [],
            },
        ),
        SimpleNamespace(
            subentry_id="stop-2",
            subentry_type="stop_place",
            data={
                "stop_id": "NSR:StopPlace:2",
                "stop_place_name": "Bus terminal",
                "platform_mode": PLATFORM_MODE_SELECTED,
                "quay_ids": ["NSR:Quay:20"],
                "show_on_map": True,
                "line_whitelist": ["RUT:Line:1"],
            },
        ),
    ]

    assert _stop_configurations(config, subentries) == [
        EnturStopConfiguration(
            stops=("NSR:StopPlace:1",),
            quays=(),
            line_whitelist=(),
            expand_platforms=False,
            show_on_map=False,
            device_stop_id="NSR:StopPlace:1",
            device_stop_name="Central station",
            config_subentry_id="stop-1",
        ),
        EnturStopConfiguration(
            stops=(),
            quays=("NSR:Quay:20",),
            line_whitelist=("RUT:Line:1",),
            expand_platforms=False,
            show_on_map=True,
            device_stop_id="NSR:StopPlace:2",
            device_stop_name="Bus terminal",
            config_subentry_id="stop-2",
        ),
    ]


async def test_async_setup_entry_applies_route_filter_per_stop(
    hass: HomeAssistant,
) -> None:
    """Test that each subentry gets an Entur client with its own filter."""
    config = PLATFORM_SCHEMA({"platform": "entur_public_transport", "stop_ids": []})
    subentries = [
        SimpleNamespace(
            subentry_id="stop-1",
            subentry_type="stop_place",
            data={
                "stop_id": "NSR:StopPlace:1",
                "line_whitelist": ["RUT:Line:1"],
            },
        ),
        SimpleNamespace(
            subentry_id="stop-2",
            subentry_type="stop_place",
            data={
                "stop_id": "NSR:StopPlace:2",
                "line_whitelist": ["SKY:Line:2"],
            },
        ),
    ]
    first_api = Mock()
    second_api = Mock()
    for api, stop_id in (
        (first_api, "NSR:StopPlace:1"),
        (second_api, "NSR:StopPlace:2"),
    ):
        api.expand_all_quays = AsyncMock()
        api.update = AsyncMock()
        api.all_stop_places_quays.return_value = [stop_id]
        api.get_stop_info.return_value = SimpleNamespace(name=stop_id)

    add_entities = Mock()
    with (
        patch(
            "homeassistant.components.entur_public_transport.sensor.EnturPublicTransportData",
            side_effect=[first_api, second_api],
        ) as data_class,
        patch(
            "homeassistant.components.entur_public_transport.sensor.async_get_clientsession",
            return_value=Mock(),
        ),
    ):
        await _async_setup(hass, config, add_entities, subentries)

    assert [call.kwargs["line_whitelist"] for call in data_class.call_args_list] == [
        ["RUT:Line:1"],
        ["SKY:Line:2"],
    ]
    assert len(add_entities.call_args_list) == 2
    for call, stop_id, subentry_id in zip(
        add_entities.call_args_list,
        ("NSR:StopPlace:1", "NSR:StopPlace:2"),
        ("stop-1", "stop-2"),
        strict=True,
    ):
        entity = call.args[0][0]
        assert entity.unique_id == stop_id
        assert entity.device_info["identifiers"] == {(DOMAIN, stop_id)}
        assert entity.device_info["name"] == f"Entur {stop_id}"
        assert call.kwargs["config_subentry_id"] == subentry_id


async def test_sensor_update_sets_departure_attributes() -> None:
    """Test that the first departures are exposed as sensor state attributes."""
    now = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    first_call = SimpleNamespace(
        expected_departure_time=now + timedelta(minutes=5),
        front_display="1 City centre",
        line_id="RUT:Line:1",
        is_realtime=True,
        delay_in_min=1,
        transport_mode="bus",
    )
    second_call = SimpleNamespace(
        expected_departure_time=now + timedelta(minutes=20),
        front_display="1 City centre",
        line_id="RUT:Line:1",
        is_realtime=False,
        delay_in_min=0,
        transport_mode="bus",
    )
    third_call = SimpleNamespace(
        expected_departure_time=now + timedelta(minutes=30),
        front_display="2 Airport",
        line_id="RUT:Line:2",
        is_realtime=False,
        delay_in_min=0,
        transport_mode="bus",
    )
    api = Mock()
    api.async_update = AsyncMock()
    api.get_stop_info.return_value = SimpleNamespace(
        latitude=59.91,
        longitude=10.75,
        estimated_calls=[first_call, second_call, third_call],
    )
    sensor = EnturPublicTransportSensor(
        api, "Transport Central station", "NSR:StopPlace:1", True
    )

    with patch(
        "homeassistant.components.entur_public_transport.sensor.dt_util.now",
        return_value=now,
    ):
        await sensor.async_update()

    assert sensor.native_value == 5
    assert sensor.icon == "mdi:bus"
    assert sensor.extra_state_attributes == {
        "stop_id": "NSR:StopPlace:1",
        "latitude": 59.91,
        "longitude": 10.75,
        "route": "1 City centre",
        "route_id": "RUT:Line:1",
        "due_at": "12:05",
        "real_time": True,
        "delay": 1,
        "next_route": "1 City centre",
        "next_route_id": "RUT:Line:1",
        "next_due_at": "12:20",
        "next_due_in": "20 min",
        "next_real_time": False,
        "next_delay": 0,
        "departure_#3": "ca. 12:30 2 Airport",
    }
    api.async_update.assert_awaited_once()
