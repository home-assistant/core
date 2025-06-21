"""Test the NUMBER platform from air-Q integration."""

from unittest.mock import AsyncMock, patch

from aioairq import AirQ, DeviceInfo
import pytest

from homeassistant.components.airq import AirQCoordinator
from homeassistant.components.airq.number import AirQLEDBrightness
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

INIT_BRIGHTNESS = 42
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
        AirQ, "get_current_brightness", AsyncMock(return_value=INIT_BRIGHTNESS)
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


async def test_entity_updates_its_native_value_upon_coordinators_update(
    number_entity: AirQLEDBrightness,
) -> None:
    """Test that the entity updates its naitve value in coorinator's update."""
    new_brightness = (number_entity.native_value + 10) % 100
    with patch("aioairq.AirQ.get_current_brightness", return_value=new_brightness):
        await number_entity.coordinator._async_update_data()
    assert number_entity.native_value == new_brightness


async def test_set_native_value_triggers_api_and_refresh(
    number_entity: AirQLEDBrightness,
) -> None:
    """Test that entity calls correct API and requests a refresh upon setting its value.

    Since set_current_brightness changes the state of the device, one cannot test
    that the correct value is set.
    """

    # pick a different value
    new_brightness = (number_entity.native_value + 10) % 100

    # spy on the two methods we care about
    with (
        patch.object(
            number_entity.coordinator.airq,
            "set_current_brightness",
            new_callable=AsyncMock,
        ) as api_spy,
        patch.object(
            number_entity.coordinator, "async_request_refresh", new_callable=AsyncMock
        ) as refresh_spy,
    ):
        # run the method under test
        await number_entity.async_set_native_value(new_brightness)

        # verify our two calls
        api_spy.assert_awaited_once_with(new_brightness)
        refresh_spy.assert_awaited_once()
