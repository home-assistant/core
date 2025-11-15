"""Tests for Mill climate."""

from datetime import timedelta
from unittest.mock import AsyncMock

from mill import Heater, Mill
from mill_local import Mill as MillLocal, OperationMode

from homeassistant.components.climate import HVACMode
from homeassistant.components.mill.climate import LocalMillHeater, MillHeater
from homeassistant.components.mill.const import DOMAIN
from homeassistant.components.mill.coordinator import MillDataUpdateCoordinator
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def create_heater(
    hass: HomeAssistant,
) -> MillHeater:
    """Creates a Mill (cloud) Heater ready to test functions on."""
    entry = MockConfigEntry(domain=DOMAIN)

    mill_data_connection = Mill("", "", websession=AsyncMock())
    mill_data_connection.fetch_heater_and_sensor_data = AsyncMock(return_value=None)

    coordinator = MillDataUpdateCoordinator(
        hass,
        entry,
        mill_data_connection=mill_data_connection,
        update_interval=timedelta(hours=1),
    )
    coordinator.async_request_refresh = AsyncMock(return_value=None)

    heater = Heater(
        name="heater_name",
        device_id="dev_id",
        is_heating=False,
        power_status=False,
        current_temp=20.0,
        set_temp=20.0,
    )

    coordinator.mill_data_connection.devices = {heater.device_id: heater}
    coordinator.mill_data_connection.set_heater_temp = AsyncMock()
    coordinator.mill_data_connection.heater_control = AsyncMock()

    mill_heater = MillHeater(coordinator=coordinator, device=heater)

    mill_heater._update_attr(heater)

    return mill_heater


async def create_local_heater(
    hass: HomeAssistant,
) -> LocalMillHeater:
    """Creates a Mill (local) Heater ready to test functions on."""
    entry = MockConfigEntry(domain=DOMAIN)

    mill_data_connection = MillLocal("", websession=AsyncMock())
    mill_data_connection.fetch_heater_and_sensor_data = AsyncMock(return_value=None)
    mill_data_connection._status["mac_address"] = "dead:beef"

    coordinator = MillDataUpdateCoordinator(
        hass,
        entry,
        mill_data_connection=mill_data_connection,
        update_interval=timedelta(hours=1),
    )
    coordinator.async_request_refresh = AsyncMock(return_value=None)
    coordinator.data = {
        "set_temperature": 20.0,
        "ambient_temperature": 20.0,
        "operation_mode": OperationMode.OFF.value,
    }

    coordinator.mill_data_connection.set_target_temperature = AsyncMock()
    coordinator.mill_data_connection.set_operation_mode_control_individually = (
        AsyncMock()
    )
    coordinator.mill_data_connection.set_operation_mode_off = AsyncMock()

    return LocalMillHeater(coordinator=coordinator)


async def test_set_hvac_mode_heat(
    hass: HomeAssistant,
) -> None:
    """Tests setting the HVAC mode HEAT."""
    mill_heater = await create_heater(hass)

    await mill_heater.async_set_hvac_mode(hvac_mode=HVACMode.HEAT)

    mill_heater.coordinator.mill_data_connection.heater_control.assert_called_once_with(
        mill_heater._id, power_status=True
    )


async def test_set_hvac_mode_off(
    hass: HomeAssistant,
) -> None:
    """Tests setting the HVAC mode OFF."""
    mill_heater = await create_heater(hass)

    await mill_heater.async_set_hvac_mode(hvac_mode=HVACMode.OFF)

    mill_heater.coordinator.mill_data_connection.heater_control.assert_called_once_with(
        mill_heater._id, power_status=False
    )


async def test_set_temperature_hvac_heat(
    hass: HomeAssistant,
) -> None:
    """Tests setting a temperature with HVAC mode HEAT."""
    mill_heater = await create_heater(hass)

    temperature = 25

    await mill_heater.async_set_temperature(
        temperature=temperature, hvac_mode=HVACMode.HEAT
    )

    mill = mill_heater.coordinator.mill_data_connection

    mill.set_heater_temp.assert_called_once_with(mill_heater._id, float(temperature))
    mill.heater_control.assert_called_once_with(mill_heater._id, power_status=True)


async def test_set_temperature_hvac_off(
    hass: HomeAssistant,
) -> None:
    """Tests setting a temperature with HVAC mode OFF."""
    mill_heater = await create_heater(hass)

    temperature = 25

    await mill_heater.async_set_temperature(
        temperature=temperature, hvac_mode=HVACMode.OFF
    )

    mill = mill_heater.coordinator.mill_data_connection

    mill.set_heater_temp.assert_called_once_with(mill_heater._id, float(temperature))
    mill.heater_control.assert_called_once_with(mill_heater._id, power_status=False)


async def test_set_temperature_no_hvac(
    hass: HomeAssistant,
) -> None:
    """Tests setting a temperature with no HVAC mode."""
    mill_heater = await create_heater(hass)

    temperature = 25

    await mill_heater.async_set_temperature(temperature=temperature)

    mill = mill_heater.coordinator.mill_data_connection

    mill.set_heater_temp.assert_called_once_with(mill_heater._id, float(temperature))
    mill.heater_control.assert_not_called()


async def test_local_set_hvac_mode_heat(
    hass: HomeAssistant,
) -> None:
    """Tests locally setting a temperature with HVAC mode HEAT."""
    local_heater = await create_local_heater(hass)

    await local_heater.async_set_hvac_mode(HVACMode.HEAT)

    mill = local_heater.coordinator.mill_data_connection

    mill.set_operation_mode_control_individually.assert_called_once_with()
    mill.set_operation_mode_off.assert_not_called()


async def test_local_set_hvac_mode_off(
    hass: HomeAssistant,
) -> None:
    """Tests locally setting a temperature with HVAC mode HEAT."""
    local_heater = await create_local_heater(hass)

    await local_heater.async_set_hvac_mode(HVACMode.OFF)

    mill = local_heater.coordinator.mill_data_connection

    mill.set_operation_mode_control_individually.assert_not_called()
    mill.set_operation_mode_off.assert_called_once_with()


async def test_local_set_temperature_hvac_heat(
    hass: HomeAssistant,
) -> None:
    """Tests locally setting a temperature with HVAC mode HEAT."""
    local_heater = await create_local_heater(hass)

    temperature = 25

    await local_heater.async_set_temperature(
        temperature=temperature, hvac_mode=HVACMode.HEAT
    )

    mill = local_heater.coordinator.mill_data_connection

    mill.set_target_temperature.assert_called_once_with(float(temperature))
    mill.set_operation_mode_control_individually.assert_called_once_with()
    mill.set_operation_mode_off.assert_not_called()


async def test_local_set_temperature_hvac_off(
    hass: HomeAssistant,
) -> None:
    """Tests locally setting a temperature with HVAC mode OFF."""
    local_heater = await create_local_heater(hass)

    temperature = 25

    await local_heater.async_set_temperature(
        temperature=temperature, hvac_mode=HVACMode.OFF
    )

    mill = local_heater.coordinator.mill_data_connection

    mill.set_target_temperature.assert_called_once_with(float(temperature))
    mill.set_operation_mode_control_individually.assert_not_called()
    mill.set_operation_mode_off.assert_called_once_with()


async def test_local_set_temperature_no_hvac(
    hass: HomeAssistant,
) -> None:
    """Tests locally setting a temperature with no HVAC mode."""
    local_heater = await create_local_heater(hass)

    temperature = 25

    await local_heater.async_set_temperature(temperature=temperature)

    mill = local_heater.coordinator.mill_data_connection

    mill.set_target_temperature.assert_called_once_with(float(temperature))
    mill.set_operation_mode_control_individually.assert_not_called()
    mill.set_operation_mode_off.assert_not_called()
