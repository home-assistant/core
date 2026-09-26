"""A19-C1 units, capabilities, and confirmed native state."""

import asyncio
from collections.abc import Generator
from datetime import timedelta
import ssl
from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from ha_xthings_cloud import XthingsCloudApiError, XthingsCloudAuthError
from ha_xthings_cloud.bulb import NativeBulbRoute
import pytest

from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant

from . import get_device_by_id, setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed

NATIVE_STATE = {"pw": 1, "br": 26, "ct": 1, "tp": 100, "hu": 0, "sa": 0, "li": 0}


async def test_native_route_auth_failure_starts_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
) -> None:
    """Rejected account credentials during native discovery start reauthentication."""
    get_device_by_id(mock_api_client, "dev_light_001")["model"] = "A19-C1"
    mock_config_entry = MockConfigEntry(
        domain="xthings_cloud",
        data=mock_config_entry.data,
        options={"native_mqtt": True},
    )
    mock_api_client.async_get_native_bulb_routes.side_effect = XthingsCloudAuthError(
        "Invalid token"
    )
    with patch(
        "homeassistant.components.xthings_cloud.coordinator.create_bulb_ssl_context",
        return_value=ssl.create_default_context(),
    ):
        await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == mock_config_entry.entry_id


@pytest.mark.parametrize(
    ("tls_error", "route_error"),
    [
        pytest.param(OSError("Unreadable certificate"), None, id="tls"),
        pytest.param(None, XthingsCloudApiError("Discovery failed"), id="routes"),
    ],
)
async def test_native_setup_failure_isolated_and_recovers(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
    mock_websocket: AsyncMock,
    tls_error: OSError | None,
    route_error: XthingsCloudApiError | None,
) -> None:
    """Optional native setup failures leave other devices usable and retry later."""
    get_device_by_id(mock_api_client, "dev_light_001")["model"] = "A19-C1"
    mock_config_entry = MockConfigEntry(
        domain="xthings_cloud",
        data=mock_config_entry.data,
        options={"native_mqtt": True},
    )
    mock_api_client.async_get_native_bulb_routes.return_value = {"dev_light_001": 123}
    mock_api_client.async_get_native_bulb_routes.side_effect = route_error
    with (
        patch(
            "homeassistant.components.xthings_cloud.coordinator.NativeBulbClient",
            autospec=True,
        ) as cls,
        patch(
            "homeassistant.components.xthings_cloud.coordinator.create_bulb_ssl_context",
            return_value=ssl.create_default_context(),
            side_effect=tls_error,
        ) as load_tls,
    ):
        cls.return_value.state = dict(NATIVE_STATE)
        await setup_integration(hass, mock_config_entry)
        assert mock_config_entry.state is ConfigEntryState.LOADED
        assert hass.states.get("light.bedroom_light").state == "unavailable"
        assert hass.states.get("light.hallway_light").state == "off"
        cls.assert_not_called()
        await hass.services.async_call(
            "light", "turn_on", {"entity_id": "light.hallway_light"}, blocking=True
        )
        mock_api_client.async_brite_on.assert_awaited_once_with("dev_light_002")
        mock_websocket.call_args.kwargs["on_device_status"](
            "dev_light_002", {"on": True}
        )
        assert hass.states.get("light.hallway_light").state == "on"

        load_tls.side_effect = None
        mock_api_client.async_get_native_bulb_routes.side_effect = None
        await mock_config_entry.runtime_data.async_refresh()
        assert hass.states.get("light.bedroom_light").state == "on"
        assert (
            hass.states.get("light.bedroom_light").attributes["color_temp_kelvin"]
            == 6500
        )


async def test_a19_capabilities_without_temperature(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
) -> None:
    """Missing startup readings do not remove hardware capabilities."""
    device = get_device_by_id(mock_api_client, "dev_light_001")
    device["model"] = "A19-C1"
    device["status"].pop("temperature")
    device["status"]["color_type"] = 1
    await setup_integration(hass, mock_config_entry)
    state = hass.states.get("light.bedroom_light")
    assert state.attributes["supported_color_modes"] == ["color_temp", "hs"]
    assert state.attributes["color_temp_kelvin"] is None
    assert state.attributes["min_color_temp_kelvin"] == 2700


@pytest.mark.parametrize(("kelvin", "native"), [(2700, 1), (6500, 100)])
async def test_a19_temperature_native_units(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
    kelvin: int,
    native: int,
) -> None:
    """HA temperature endpoints map to the app's native slider endpoints."""
    device = get_device_by_id(mock_api_client, "dev_light_001")
    device["model"] = "A19-C1"
    device["status"]["temperature"] = native
    device["status"]["color_type"] = 1
    await setup_integration(hass, mock_config_entry)
    assert (
        hass.states.get("light.bedroom_light").attributes["color_temp_kelvin"] == kelvin
    )
    await hass.services.async_call(
        "light",
        "turn_on",
        {
            "entity_id": "light.bedroom_light",
            "color_temp_kelvin": kelvin,
        },
        blocking=True,
    )
    mock_api_client.async_brite_color.assert_called_once_with(
        "dev_light_001",
        {"colortype": 1, "temperature": native, "brightness": 75},
    )


async def test_native_readback_survives_http_poll_and_ws(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
    mock_websocket: AsyncMock,
) -> None:
    """Confirmed MQTT state wins over stale HTTP and partial websocket reports."""
    get_device_by_id(mock_api_client, "dev_light_001")["model"] = "A19-C1"
    mock_config_entry = MockConfigEntry(
        domain="xthings_cloud",
        data=mock_config_entry.data,
        options={
            "native_mqtt": True,
        },
    )
    mock_api_client.async_get_native_bulb_routes.return_value = {"dev_light_001": 123}
    with (
        patch(
            "homeassistant.components.xthings_cloud.coordinator.NativeBulbClient",
            autospec=True,
        ) as cls,
        patch(
            "homeassistant.components.xthings_cloud.coordinator.create_bulb_ssl_context",
            return_value=ssl.create_default_context(),
        ),
    ):
        bulb = cls.return_value
        bulb.state = dict(NATIVE_STATE)
        await setup_integration(hass, mock_config_entry)
        assert (
            hass.states.get("light.bedroom_light").attributes["color_temp_kelvin"]
            == 6500
        )
        await mock_config_entry.runtime_data.async_refresh()
        mock_websocket.call_args.kwargs["on_device_status"](
            "dev_light_001", {"temperature": 1}
        )
        assert (
            hass.states.get("light.bedroom_light").attributes["color_temp_kelvin"]
            == 6500
        )
        await hass.services.async_call(
            "light",
            "turn_on",
            {
                "entity_id": "light.bedroom_light",
                "color_temp_kelvin": 2700,
            },
            blocking=True,
        )
        bulb.async_set_state.assert_awaited_once_with({"pw": 1, "ct": 1, "tp": 1})
        mock_api_client.async_brite_color.assert_not_awaited()
        cls.call_args.args[3](None)
        assert hass.states.get("light.bedroom_light").state == "unavailable"
        cls.call_args.args[3](dict(NATIVE_STATE))
        assert hass.states.get("light.bedroom_light").state == "on"
        await hass.config_entries.async_unload(mock_config_entry.entry_id)
        bulb.async_stop.assert_awaited()


async def test_native_reports_do_not_postpone_account_refresh(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
) -> None:
    """Frequent device reports must not indefinitely postpone cloud discovery."""
    get_device_by_id(mock_api_client, "dev_light_001")["model"] = "A19-C1"
    mock_config_entry = MockConfigEntry(
        domain="xthings_cloud",
        data=mock_config_entry.data,
        options={
            "native_mqtt": True,
        },
    )
    mock_api_client.async_get_native_bulb_routes.return_value = {"dev_light_001": 123}
    with (
        patch(
            "homeassistant.components.xthings_cloud.coordinator.NativeBulbClient",
            autospec=True,
        ) as cls,
        patch(
            "homeassistant.components.xthings_cloud.coordinator.create_bulb_ssl_context",
            return_value=ssl.create_default_context(),
        ),
    ):
        cls.return_value.state = dict(NATIVE_STATE)
        await setup_integration(hass, mock_config_entry)
        freezer.tick(timedelta(minutes=29))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        cls.call_args.args[3](dict(NATIVE_STATE))
        freezer.tick(timedelta(minutes=2))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert mock_api_client.async_get_devices.await_count == 2


async def test_native_startup_without_reply_is_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
) -> None:
    """An online HTTP cache does not prove that the bulb is reachable."""
    get_device_by_id(mock_api_client, "dev_light_001")["model"] = "A19-C1"
    mock_config_entry = MockConfigEntry(
        domain="xthings_cloud",
        data=mock_config_entry.data,
        options={
            "native_mqtt": True,
        },
    )
    mock_api_client.async_get_native_bulb_routes.return_value = {"dev_light_001": 123}
    with (
        patch(
            "homeassistant.components.xthings_cloud.coordinator.NativeBulbClient",
            autospec=True,
        ) as cls,
        patch(
            "homeassistant.components.xthings_cloud.coordinator.create_bulb_ssl_context",
            return_value=ssl.create_default_context(),
        ),
    ):
        cls.return_value.state = None
        await setup_integration(hass, mock_config_entry)
        state = hass.states.get("light.bedroom_light")
        assert state.state == "unavailable"
        assert state.attributes["supported_color_modes"] == ["color_temp", "hs"]
        assert state.attributes.get("color_temp_kelvin") is None
        assert hass.states.get("light.hallway_light").state == "off"


@pytest.mark.parametrize(
    ("hs_color", "brightness", "native_color", "reported_hs", "reported_brightness"),
    [
        pytest.param(
            (0, 100), {}, {"hu": 0, "sa": 100, "li": 50}, (0, 100), 66, id="red"
        ),
        pytest.param(
            (120, 50),
            {},
            {"hu": 120, "sa": 100, "li": 75},
            (120, 50),
            66,
            id="pale-green",
        ),
        pytest.param(
            (240, 0), {}, {"hu": 0, "sa": 0, "li": 100}, (0, 0), 66, id="white"
        ),
        pytest.param(
            (240, 100),
            {"brightness": 102},
            {"hu": 240, "sa": 100, "li": 50, "br": 40},
            (240, 100),
            102,
            id="blue-with-brightness",
        ),
    ],
)
async def test_native_color_commands_and_confirmed_readback(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
    hs_color: tuple[int, int],
    brightness: dict[str, int],
    native_color: dict[str, int],
    reported_hs: tuple[int, int],
    reported_brightness: int,
) -> None:
    """HA HSV colors convert to native HSL without conflating brightness/lightness."""
    get_device_by_id(mock_api_client, "dev_light_001")["model"] = "A19-C1"
    mock_config_entry = MockConfigEntry(
        domain="xthings_cloud",
        data=mock_config_entry.data,
        options={"native_mqtt": True},
    )
    mock_api_client.async_get_native_bulb_routes.return_value = {"dev_light_001": 123}
    with (
        patch(
            "homeassistant.components.xthings_cloud.coordinator.NativeBulbClient",
            autospec=True,
        ) as cls,
        patch(
            "homeassistant.components.xthings_cloud.coordinator.create_bulb_ssl_context",
            return_value=ssl.create_default_context(),
        ),
    ):
        cls.return_value.state = dict(NATIVE_STATE)
        await setup_integration(hass, mock_config_entry)
        await hass.services.async_call(
            "light",
            "turn_on",
            {"entity_id": "light.bedroom_light", "hs_color": hs_color, **brightness},
            blocking=True,
        )
        cls.return_value.async_set_state.assert_awaited_once_with(
            {"pw": 1, "ct": 0, **native_color}
        )
        mock_api_client.async_brite_color.assert_not_awaited()
        assert (
            hass.states.get("light.bedroom_light").attributes["color_mode"]
            == "color_temp"
        )
        cls.call_args.args[3]({**NATIVE_STATE, "ct": 0, **native_color})
        state = hass.states.get("light.bedroom_light")
        assert state.attributes["color_mode"] == "hs"
        assert state.attributes["hs_color"] == pytest.approx(reported_hs)
        assert state.attributes["brightness"] == reported_brightness


def _native_entry(mock_config_entry: MockConfigEntry) -> MockConfigEntry:
    return MockConfigEntry(
        domain="xthings_cloud",
        data=mock_config_entry.data,
        options={"native_mqtt": True},
    )


@pytest.fixture
def mock_native_client() -> Generator[MagicMock]:
    """Patch the native bulb client class and its bundled TLS credentials."""
    with (
        patch(
            "homeassistant.components.xthings_cloud.coordinator.NativeBulbClient",
            autospec=True,
        ) as cls,
        patch(
            "homeassistant.components.xthings_cloud.coordinator.create_bulb_ssl_context",
            return_value=ssl.create_default_context(),
        ),
    ):
        yield cls


async def test_native_availability_survives_account_poll_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
    mock_native_client: MagicMock,
) -> None:
    """A confirmed native bulb stays usable while the HTTP account poll fails."""
    get_device_by_id(mock_api_client, "dev_light_001")["model"] = "A19-C1"
    mock_config_entry = _native_entry(mock_config_entry)
    mock_api_client.async_get_native_bulb_routes.return_value = {"dev_light_001": 123}
    cls = mock_native_client
    cls.return_value.state = dict(NATIVE_STATE)
    await setup_integration(hass, mock_config_entry)
    mock_api_client.async_get_devices.side_effect = XthingsCloudApiError(
        "temporary HTTP failure"
    )
    await mock_config_entry.runtime_data.async_refresh()
    # HTTP devices follow the failed poll; the native bulb reports itself.
    assert hass.states.get("light.hallway_light").state == "unavailable"
    cls.call_args.args[3](dict(NATIVE_STATE))
    assert hass.states.get("light.bedroom_light").state == "on"
    cls.call_args.args[3](None)
    assert hass.states.get("light.bedroom_light").state == "unavailable"


async def test_unavailable_native_bulb_rediscovers_changed_route(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
    mock_native_client: MagicMock,
) -> None:
    """A bulb moved into an Xthings group recovers without a manual reload."""
    get_device_by_id(mock_api_client, "dev_light_001")["model"] = "A19-C1"
    mock_config_entry = _native_entry(mock_config_entry)
    mock_api_client.async_get_native_bulb_routes.return_value = {
        "dev_light_001": NativeBulbRoute(123)
    }
    cls = mock_native_client
    cls.return_value.state = dict(NATIVE_STATE)
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data
    old_bulb = coordinator.native_bulbs["dev_light_001"]

    # A healthy bulb does not trigger discovery on each account poll.
    await coordinator.async_refresh()
    assert mock_api_client.async_get_native_bulb_routes.await_count == 1

    new_route = NativeBulbRoute(123, "new-group")
    mock_api_client.async_get_native_bulb_routes.return_value = {
        "dev_light_001": new_route
    }
    cls.return_value.state = None
    await coordinator.async_refresh()
    assert mock_api_client.async_get_native_bulb_routes.await_count == 2
    old_bulb.async_stop.assert_awaited()
    assert cls.call_args.args[1] == new_route
    assert cls.call_count == 2

    # An unchanged route keeps the existing client.
    await coordinator.async_refresh()
    assert cls.call_count == 2


async def test_unload_during_native_discovery_creates_no_clients(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
    mock_native_client: MagicMock,
) -> None:
    """Discovery finishing after unload must not start native clients."""
    get_device_by_id(mock_api_client, "dev_light_001")["model"] = "A19-C1"
    mock_config_entry = _native_entry(mock_config_entry)
    mock_api_client.async_get_native_bulb_routes.side_effect = XthingsCloudApiError(
        "initial failure"
    )
    cls = mock_native_client
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data
    started, release = asyncio.Event(), asyncio.Event()

    async def discover() -> dict[str, NativeBulbRoute]:
        started.set()
        await release.wait()
        return {"dev_light_001": NativeBulbRoute(123)}

    mock_api_client.async_get_native_bulb_routes.side_effect = discover
    refresh = hass.async_create_task(coordinator.async_refresh())
    await started.wait()
    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    release.set()
    await refresh
    assert not coordinator.native_bulbs
    cls.assert_not_called()


async def test_native_retry_is_not_postponed_by_websocket_updates(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
    mock_websocket: AsyncMock,
    mock_native_client: MagicMock,
) -> None:
    """Frequent updates from other devices must not postpone native recovery."""
    get_device_by_id(mock_api_client, "dev_light_001")["model"] = "A19-C1"
    mock_config_entry = _native_entry(mock_config_entry)
    mock_api_client.async_get_native_bulb_routes.side_effect = XthingsCloudApiError(
        "Discovery failed"
    )
    cls = mock_native_client
    cls.return_value.state = dict(NATIVE_STATE)
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get("light.bedroom_light").state == "unavailable"
    mock_api_client.async_get_native_bulb_routes.side_effect = None
    mock_api_client.async_get_native_bulb_routes.return_value = {"dev_light_001": 123}
    for _ in range(3):
        freezer.tick(timedelta(minutes=4))
        mock_websocket.call_args.kwargs["on_device_status"](
            "dev_light_002", {"on": True}
        )
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
    assert mock_api_client.async_get_native_bulb_routes.await_count == 2
    assert hass.states.get("light.bedroom_light").state == "on"


async def test_native_option_change_reloads_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
    mock_native_client: MagicMock,
) -> None:
    """Toggling native MQTT reloads the entry; token updates do not."""
    get_device_by_id(mock_api_client, "dev_light_001")["model"] = "A19-C1"
    mock_api_client.async_get_native_bulb_routes.return_value = {"dev_light_001": 123}
    cls = mock_native_client
    cls.return_value.state = dict(NATIVE_STATE)
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data
    cls.assert_not_called()

    hass.config_entries.async_update_entry(
        mock_config_entry, data={**mock_config_entry.data, "token": "new-token"}
    )
    await hass.async_block_till_done()
    assert mock_config_entry.runtime_data is coordinator

    hass.config_entries.async_update_entry(
        mock_config_entry, options={"native_mqtt": True}
    )
    await hass.async_block_till_done()
    assert mock_config_entry.runtime_data is not coordinator
    assert mock_config_entry.state is ConfigEntryState.LOADED
    cls.assert_called_once()

    native = mock_config_entry.runtime_data
    bulb = native.native_bulbs["dev_light_001"]
    hass.config_entries.async_update_entry(
        mock_config_entry, options={"native_mqtt": False}
    )
    await hass.async_block_till_done()
    bulb.async_stop.assert_awaited()
    assert not mock_config_entry.runtime_data.native_bulbs
