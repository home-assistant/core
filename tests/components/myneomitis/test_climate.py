"""Tests for the MyNeomitis climate integration."""

from unittest.mock import AsyncMock, Mock

from climate.const import HVACMode
import pytest

from homeassistant.components.myneomitis.climate import (
    SUPPORT_FLAGS,
    MyNeoClimate,
    async_setup_entry,
)
from homeassistant.components.myneomitis.const import DOMAIN
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant


@pytest.fixture
def sample_devices() -> list[dict]:
    """Provide sample device data for testing."""
    return [
        {
            "_id": "dev1",
            "name": "Salon",
            "model": "EV30",
            "state": {
                "overrideTemp": 21.5,
                "currentTemp": 20.0,
                "comfLimitMin": 7,
                "comfLimitMax": 30,
                "targetMode": 0,
            },
            "parents": "",
            "connected": True,
            "program": {"data": {}},
        },
        {
            "_id": "dev2",
            "name": "Chamber",
            "model": "NTD",
            "state": {
                "targetTemp": 19.0,
                "currentTemp": 18.0,
                "comfLimitMin": 5,
                "comfLimitMax": 25,
                "targetMode": 2,
            },
            "parents": "gateway",
            "connected": True,
            "program": {"data": {}},
        },
    ]


@pytest.fixture
def basic_device() -> dict:
    """Casual principal device fixture."""
    return {
        "_id": "d1",
        "name": "Test",
        "model": "EV30",
        "state": {
            "overrideTemp": 22.0,
            "currentTemp": 21.0,
            "comfLimitMin": 7,
            "comfLimitMax": 30,
            "targetMode": 0,
        },
        "parents": "",
        "connected": True,
        "program": {"data": {}},
    }


@pytest.fixture
def sub_device() -> dict:
    """Casual sub-device fixture."""
    return {
        "_id": "d2",
        "rfid": "r1",
        "name": "Sub",
        "model": "NTD",
        "state": {
            "targetTemp": 18.5,
            "currentTemp": 17.5,
            "comfLimitMin": 5,
            "comfLimitMax": 25,
            "targetMode": 1,
        },
        "parents": "gateway",
        "connected": True,
        "program": {"data": {}},
    }


@pytest.fixture
def fake_api() -> Mock:
    """Fake API with no-op listener registration."""
    api = Mock()
    api.sio.connected = True
    api.register_listener = lambda *args: None
    return api


@pytest.mark.asyncio
async def test_climate_entities_created(
    hass: HomeAssistant, sample_devices: list[dict]
) -> None:
    """Test that climate entities are created correctly from sample devices."""
    hass.data.setdefault(DOMAIN, {})["climate-test"] = {
        "api": (fake_api := Mock()),
        "devices": sample_devices,
    }
    fake_api.sio.connected = True
    fake_api.register_listener = lambda _id, cb: None

    added: list[MyNeoClimate] = []
    await async_setup_entry(
        hass,
        type("E", (), {"entry_id": "climate-test"}),
        added.extend,
    )

    assert len(added) == 2
    salon, chamber = added

    assert salon.name == "MyNeo Salon"
    assert salon.unique_id == "myneo_dev1"
    assert salon.temperature_unit == UnitOfTemperature.CELSIUS
    assert salon.min_temp == 7
    assert salon.max_temp == 30
    assert pytest.approx(salon.current_temperature, 0.1) == 20.0
    assert pytest.approx(salon.target_temperature, 0.1) == 21.5
    assert salon.hvac_mode in (HVACMode.HEAT, HVACMode.OFF)
    assert "boost" in salon.preset_modes

    assert chamber.name == "MyNeo Chamber"
    assert chamber.unique_id == "myneo_dev2"
    assert chamber.min_temp == 5
    assert chamber.max_temp == 25
    assert pytest.approx(chamber.current_temperature, 0.1) == 18.0
    assert pytest.approx(chamber.target_temperature, 0.1) == 19.0
    assert chamber.hvac_mode in (HVACMode.HEAT, HVACMode.OFF)
    assert "eco" in chamber.preset_modes


@pytest.mark.asyncio
async def test_handle_ws_update_changes_state(
    hass: HomeAssistant, sample_devices: list[dict]
) -> None:
    """Test that WebSocket updates correctly change the state of the entity."""
    fake_api = Mock()
    fake_api.sio.connected = False
    fake_api.register_listener = lambda _id, cb: None

    device = sample_devices[0].copy()
    ent = MyNeoClimate(fake_api, device, sample_devices)
    ent.hass = hass
    ent.async_write_ha_state = lambda: None

    new_state = {
        "currentTemp": 22.0,
        "overrideTemp": 23.0,
        "targetMode": 4,
        "changeOverUser": 0,
        "name": "Salon Modifié",
    }
    ent.handle_ws_update(new_state)

    assert pytest.approx(ent.current_temperature, 0.1) == 22.0
    assert pytest.approx(ent.target_temperature, 0.1) == 23.0
    assert ent.hvac_mode == HVACMode.OFF
    assert ent.name == "Salon Modifié"


@pytest.mark.asyncio
async def test_extra_state_attributes_includes_ws_and_program(
    sample_devices: list[dict],
) -> None:
    """Test that extra state attributes include WebSocket status and program data."""
    fake_api = Mock()
    fake_api.sio.connected = False
    fake_api.register_listener = lambda _id, cb: None

    device = sample_devices[1].copy()
    device["program"] = {"data": {"Monday": [{"hour": 8, "temp": 18}]}}

    ent = MyNeoClimate(fake_api, device, sample_devices)
    attrs = ent.extra_state_attributes

    assert attrs["ws_status"] == "disconnected"
    assert "planning_monday" in attrs
    assert attrs["planning_monday"] is not None


@pytest.mark.asyncio
async def test_supported_features(basic_device: dict, fake_api: Mock) -> None:
    """supported_features property returns the correct bitmask."""
    ent = MyNeoClimate(fake_api, basic_device, [basic_device])
    assert ent.supported_features == SUPPORT_FLAGS


@pytest.mark.asyncio
async def test_async_set_temperature_and_write(
    basic_device: dict, fake_api: Mock
) -> None:
    """Test async_set_temperature calls API and writes HA state."""
    ent = MyNeoClimate(fake_api, basic_device, [basic_device])
    ent.async_write_ha_state = Mock()
    ent.hass = Mock()

    ent._attr_preset_mode = "eco"
    fake_api.set_device_mode = AsyncMock()
    fake_api.set_device_temperature = AsyncMock()

    await ent.async_set_temperature(**{ATTR_TEMPERATURE: 25.0})

    fake_api.set_device_mode.assert_awaited_once_with("d1", 8)
    fake_api.set_device_temperature.assert_awaited_once_with("d1", 25.0)
    assert ent._attr_target_temperature == 25.0
    ent.async_write_ha_state.assert_called_once()


@pytest.mark.asyncio
async def test_async_set_preset_mode_unknown_logs_warning(
    basic_device: dict, fake_api: Mock, caplog: pytest.LogCaptureFixture
) -> None:
    """Unknown preset mode should log a warning."""
    ent = MyNeoClimate(fake_api, basic_device, [basic_device])
    caplog.set_level("WARNING")
    ent._attr_hvac_mode = HVACMode.HEAT

    await ent.async_set_preset_mode("inconnu")
    assert "Unknown preset mode" in caplog.text


@pytest.mark.asyncio
async def test_async_set_hvac_mode_off_and_heat(
    basic_device: dict, fake_api: Mock, hass: HomeAssistant
) -> None:
    """Test async_set_hvac_mode for OFF and HEAT."""
    ent = MyNeoClimate(fake_api, basic_device, [basic_device])
    fake_api.set_device_mode = AsyncMock()
    ent.hass = hass
    ent.async_write_ha_state = lambda: None

    await ent.async_set_hvac_mode(HVACMode.OFF)

    fake_api.set_device_mode.assert_awaited_once_with("d1", 4)
    assert ent.hvac_mode == HVACMode.OFF

    fake_api.set_device_mode.reset_mock()

    await ent.async_set_hvac_mode(HVACMode.HEAT)

    fake_api.set_device_mode.assert_awaited_once_with("d1", 60)
    assert ent.hvac_mode == HVACMode.HEAT


@pytest.mark.asyncio
async def test_async_update_and_log(
    basic_device: dict, fake_api: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test async_update fetches state, logs, and writes HA state."""
    ent = MyNeoClimate(fake_api, basic_device, [basic_device])
    ent.async_write_ha_state = Mock()
    fake_api.get_device_state = AsyncMock(return_value={"state": {"currentTemp": 24.0}})

    monkeypatch.setattr(
        "homeassistant.components.myneomitis.climate.log_api_update",
        lambda *a, **k: None,
    )

    await ent.async_update()
    assert ent._attr_current_temperature == 24.0
    ent.async_write_ha_state.assert_called_once()


@pytest.mark.asyncio
async def test_set_and_get_api_device_state_sub_and_main(
    sub_device: dict, basic_device: dict, fake_api: Mock
) -> None:
    """Test set/get API device mode and temperature for both sub and main."""
    ent_sub = MyNeoClimate(fake_api, sub_device, [sub_device])
    fake_api.set_sub_device_mode = AsyncMock()
    fake_api.set_sub_device_temperature = AsyncMock()
    fake_api.get_sub_device_state = AsyncMock(
        return_value=[{"rfid": "r1", "state": {}}]
    )

    await ent_sub.set_api_device_mode("boost")
    fake_api.set_sub_device_mode.assert_awaited_once_with("gateway", "r1", 6)

    await ent_sub.set_api_device_temperature(19.5)
    fake_api.set_sub_device_temperature.assert_awaited_once_with("gateway", "r1", 19.5)

    state = await ent_sub.get_api_device_state()
    fake_api.get_sub_device_state.assert_awaited_once_with("gateway")
    assert state == {"rfid": "r1", "state": {}}

    ent_main = MyNeoClimate(fake_api, basic_device, [basic_device])
    fake_api.set_device_mode = AsyncMock()
    fake_api.set_device_temperature = AsyncMock()
    fake_api.get_device_state = AsyncMock(return_value={"state": {}})

    await ent_main.set_api_device_mode("eco")
    fake_api.set_device_mode.assert_awaited_once_with("d1", 2)

    await ent_main.set_api_device_temperature(20.5)
    fake_api.set_device_temperature.assert_awaited_once_with("d1", 20.5)

    state = await ent_main.get_api_device_state()
    fake_api.get_device_state.assert_awaited_once_with("d1")
    assert state == {"state": {}}
