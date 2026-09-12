"""Test the AirTouch 3 coordinator."""

from unittest.mock import ANY, AsyncMock, patch

from pyairtouch3 import AirTouchError
from pyairtouch3.airtouch_aircon import Aircon
from pyairtouch3.airtouch_sensor import Sensor
from pyairtouch3.airtouch_zone import AirtouchZone
from pyairtouch3.enums import ZoneStatus
import pytest

from homeassistant.components.airtouch3.const import DOMAIN
from homeassistant.components.airtouch3.coordinator import (
    AirTouch3Data,
    Airtouch3DataUpdateCoordinator,
    async_fetch_airtouch_data,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry


def _zone(
    zone_id: int,
    name: str,
    desired_temperature: int,
    status: ZoneStatus,
    current_temperature: int | None = None,
) -> AirtouchZone:
    """Create a zone fixture."""
    zone = AirtouchZone(20)
    zone.id = zone_id
    zone.name = name
    zone.desired_temperature = desired_temperature
    zone.status = status
    if current_temperature is not None:
        sensor = Sensor()
        sensor.current_temperature = current_temperature
        sensor.is_available = True
        zone.sensor = sensor
    return zone


def _aircon() -> Aircon:
    """Create AirTouch data for coordinator tests."""
    aircon = Aircon(1)
    aircon.brand_id = 2
    aircon.status = True
    aircon.zones = [
        _zone(1, "Living", 20, ZoneStatus.ZONE_ON, 23),
        _zone(2, "Bedroom", 21, ZoneStatus.ZONE_OFF),
    ]
    return aircon


def _coordinator(hass: HomeAssistant) -> Airtouch3DataUpdateCoordinator:
    """Create a coordinator with data."""
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="35901813", data={CONF_HOST: "1.1.1.1"}
    )
    entry.add_to_hass(hass)
    coordinator = Airtouch3DataUpdateCoordinator(hass, entry, "1.1.1.1")
    coordinator.data = AirTouch3Data.from_aircon(_aircon())
    return coordinator


async def test_async_fetch_airtouch_data_success() -> None:
    """Test fetching AirTouch data delegates to pyairtouch3."""
    aircon = _aircon()
    fetch_aircon = AsyncMock(return_value=aircon)

    with patch(
        "homeassistant.components.airtouch3.coordinator.AirTouchClient"
    ) as client_class:
        client_class.return_value.fetch_aircon = fetch_aircon
        result = await async_fetch_airtouch_data("1.1.1.1")

    assert result is aircon
    client_class.assert_called_once_with("1.1.1.1", 8899, logger=ANY)
    fetch_aircon.assert_awaited_once()


async def test_async_fetch_airtouch_data_error_raises_update_failed() -> None:
    """Test pyairtouch3 errors are surfaced as update failures."""
    fetch_aircon = AsyncMock(side_effect=AirTouchError("bad response"))

    with patch(
        "homeassistant.components.airtouch3.coordinator.AirTouchClient"
    ) as client_class:
        client_class.return_value.fetch_aircon = fetch_aircon
        with pytest.raises(UpdateFailed):
            await async_fetch_airtouch_data("1.1.1.1")

    fetch_aircon.assert_awaited_once()


async def test_async_fetch_airtouch_data_missing_ac_id_raises_update_failed() -> None:
    """Test incomplete pyairtouch3 data is surfaced as an update failure."""
    aircon = _aircon()
    aircon.ac_id = None

    with patch(
        "homeassistant.components.airtouch3.coordinator.AirTouchClient"
    ) as client_class:
        client_class.return_value.fetch_aircon = AsyncMock(return_value=aircon)
        with pytest.raises(UpdateFailed):
            await async_fetch_airtouch_data("1.1.1.1")


async def test_update_data_uses_parsed_response(hass: HomeAssistant) -> None:
    """Test coordinator refresh stores parsed AirTouch data."""
    coordinator = _coordinator(hass)
    parsed = _aircon()

    with patch(
        "homeassistant.components.airtouch3.coordinator.async_fetch_airtouch_data",
        AsyncMock(return_value=parsed),
    ):
        result = await coordinator._async_update_data()

    assert result.aircon is parsed
    assert result.zones == {zone.id: zone for zone in parsed.zones}
