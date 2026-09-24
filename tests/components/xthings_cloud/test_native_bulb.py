"""A19-C1 units, capabilities, and confirmed native state."""

from datetime import timedelta
import ssl
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.core import HomeAssistant

from . import get_device_by_id, setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed

NATIVE_STATE = {"pw": 1, "br": 26, "ct": 1, "tp": 100, "hu": 0, "sa": 0, "li": 0}


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
            "mqtt_certificate": "/cert",
            "mqtt_private_key": "/key",
        },
    )
    mock_api_client.async_get_native_bulb_routes.return_value = {"dev_light_001": 123}
    with (
        patch(
            "homeassistant.components.xthings_cloud.coordinator.NativeBulbClient",
            autospec=True,
        ) as cls,
        patch(
            "homeassistant.components.xthings_cloud.coordinator._load_mqtt_tls",
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
            "mqtt_certificate": "/cert",
            "mqtt_private_key": "/key",
        },
    )
    mock_api_client.async_get_native_bulb_routes.return_value = {"dev_light_001": 123}
    with (
        patch(
            "homeassistant.components.xthings_cloud.coordinator.NativeBulbClient",
            autospec=True,
        ) as cls,
        patch(
            "homeassistant.components.xthings_cloud.coordinator._load_mqtt_tls",
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
            "mqtt_certificate": "/cert",
            "mqtt_private_key": "/key",
        },
    )
    mock_api_client.async_get_native_bulb_routes.return_value = {"dev_light_001": 123}
    with (
        patch(
            "homeassistant.components.xthings_cloud.coordinator.NativeBulbClient",
            autospec=True,
        ) as cls,
        patch(
            "homeassistant.components.xthings_cloud.coordinator._load_mqtt_tls",
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
