"""Test the NUMBER platform from air-Q integration."""

from unittest.mock import AsyncMock

from aioairq import AirQ, DeviceInfo
import pytest

from homeassistant.components.airq import AirQCoordinator
from homeassistant.components.airq.number import LED_VALUE_DEFAULT, AirQLEDBrightness
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

INIT_LED_VALUE = 4.2
INIT_BRIGHTNESS_PERCENT = INIT_LED_VALUE * 10.0
TEST_DEVICE_DATA = {"co2": 500.0, "Status": "OK"}
TEST_DEVICE_INFO = DeviceInfo(
    id="id",
    name="airq_name",
    model="model",
    sw_version="sw",
    hw_version="hw",
)
TEST_USER_DATA = {
    CONF_IP_ADDRESS: "192.168.0.0",
    CONF_PASSWORD: "password",
}
ENTITY_ID = f"number.{TEST_DEVICE_INFO['name']}_led_brightness"


@pytest.fixture(autouse=True)
def patch_aioairq_api(monkeypatch: pytest.MonkeyPatch):
    """Autouse fixture to stub out the aioairq client."""
    monkeypatch.setattr(
        AirQ,
        "fetch_device_info",
        AsyncMock(return_value=TEST_DEVICE_INFO),
    )
    monkeypatch.setattr(
        AirQ,
        "get_latest_data",
        AsyncMock(return_value=TEST_DEVICE_DATA),
    )
    monkeypatch.setattr(
        AirQ,
        "get_current_brightness",
        AsyncMock(return_value=INIT_LED_VALUE),
    )


@pytest.fixture
async def number_entity(
    hass: HomeAssistant, registered_airq_config_entry: MockConfigEntry
) -> AirQLEDBrightness:
    """Set up the integration and return the LED‐brightness entity."""
    await hass.config_entries.async_setup(registered_airq_config_entry.entry_id)
    await hass.async_block_till_done()
    return hass.data["number"].get_entity(ENTITY_ID)


def test_entity_initialization_and_limits(number_entity: AirQLEDBrightness) -> None:
    """unique_id, native_min_value and native_max_value are correct."""
    coord: AirQCoordinator = number_entity.coordinator  # type: ignore[assignment]
    assert number_entity.unique_id == f"{coord.device_id}_airq_led_brightness"
    assert number_entity.native_min_value == 0.0
    assert number_entity.native_max_value == 100.0


@pytest.mark.asyncio
async def test_set_native_value_calls_api_and_updates_state(
    hass: HomeAssistant,
    number_entity: AirQLEDBrightness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """async_set_native_value must await the API, update coordinator.data, and write state."""
    # Check that the fixtures set the initial brightness as expected
    assert number_entity.native_value == INIT_BRIGHTNESS_PERCENT

    # ensure that the new brightness will be different
    new_brightness_percent = (INIT_BRIGHTNESS_PERCENT + 10.0) % 100.0
    new_led_value = new_brightness_percent / 10.0

    # spy on the API method
    spy = AsyncMock(return_value=None)
    monkeypatch.setattr(AirQ, "set_current_brightness", spy)

    # call the method under test
    await number_entity.async_set_native_value(new_brightness_percent)

    # 1) did we call the API?
    spy.assert_awaited_once_with(new_led_value)

    # 2) did the coordinator.data update?
    coord: AirQCoordinator = number_entity.coordinator  # type: ignore[assignment]
    assert coord.data["brightness"] == new_led_value
    assert number_entity.native_value == new_brightness_percent

    # 3) did HA's state machine get updated?
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert float(state.state) == new_brightness_percent


def test_default_brightness_fallback(number_entity: AirQLEDBrightness) -> None:
    """If coordinator.data has no 'brightness', native_value falls back to the default."""
    coord: AirQCoordinator = number_entity.coordinator  # type: ignore[assignment]
    coord.data.pop("brightness", None)
    assert number_entity.native_value == LED_VALUE_DEFAULT * 10.0
