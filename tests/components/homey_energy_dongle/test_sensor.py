"""Test Homey Energy Dongle sensors."""

from unittest.mock import patch

from dsmr_parser.objects import Telegram
from homey_energy_dongle_ws import ConnectionLostError
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.homeassistant import (
    DOMAIN as HOMEASSISTANT_DOMAIN,
    SERVICE_UPDATE_ENTITY,
)
from homeassistant.components.homey_energy_dongle.const import DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from . import (
    EQUIPMENT_IDENTIFIER,
    GAS_METER_IDENTIFIER,
    TELEGRAM_MBUS,
    TELEGRAM_OTHER_METER,
    TELEGRAM_Q3D,
    TELEGRAM_V2_2,
    TELEGRAM_V5,
    parse,
)
from .conftest import TelegramQueue

POWER_ENTITY_ID = "sensor.electricity_meter_power"
TARIFF_ENTITY_ID = "sensor.electricity_meter_active_tariff"
GAS_ENTITY_ID = "sensor.gas_meter_meter_reading"
IMPORTED_ENTITY_ID = "sensor.electricity_meter_total_energy_imported"

# DSMR 5 telegram with the Fluvius demand registers.
TELEGRAM_BELGIUM = TELEGRAM_V5.replace(
    "!", "1-0:1.4.0(01.750*kW)\r\n1-0:1.6.0(170102120000W)(04.326*kW)\r\n!"
)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    "telegram_data",
    [
        pytest.param(TELEGRAM_V5, id="dsmr5"),
        pytest.param(TELEGRAM_MBUS, id="mbus"),
    ],
)
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """Test the sensors created for the registers in the first telegram."""
    await snapshot_platform(hass, entity_registry, snapshot, init_integration.entry_id)


@pytest.mark.parametrize(
    "telegram_data",
    [
        "".join(
            line
            for line in TELEGRAM_V5.splitlines(keepends=True)
            if not line.startswith("0-1:")
        )
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_new_mbus_device(hass: HomeAssistant, telegrams: TelegramQueue) -> None:
    """Test a meter that shows up after setup gets its sensor."""
    assert hass.states.get(GAS_ENTITY_ID) is None

    telegrams.put_nowait(parse(TELEGRAM_V5))
    await hass.async_block_till_done()

    assert hass.states.get(GAS_ENTITY_ID).state == "0.107"


@pytest.mark.usefixtures("init_integration")
async def test_total_without_all_tariff_registers(
    hass: HomeAssistant, telegrams: TelegramQueue, telegram: Telegram
) -> None:
    """Test a telegram missing a tariff register doesn't lower the summed total."""
    assert hass.states.get(IMPORTED_ENTITY_ID).state == "6.825"

    telegrams.put_nowait(
        parse(TELEGRAM_V5.replace("1-0:1.8.2(000002.399*kWh)\r\n", ""))
    )
    await hass.async_block_till_done()
    assert hass.states.get(IMPORTED_ENTITY_ID).state == STATE_UNKNOWN

    telegrams.put_nowait(telegram)
    await hass.async_block_till_done()
    assert hass.states.get(IMPORTED_ENTITY_ID).state == "6.825"


@pytest.mark.usefixtures("init_integration")
async def test_mbus_device_missing(
    hass: HomeAssistant, telegrams: TelegramQueue
) -> None:
    """Test an M-Bus reading is unknown when its meter drops out of the telegram."""
    assert hass.states.get(GAS_ENTITY_ID).state == "0.107"

    telegrams.put_nowait(Telegram())
    await hass.async_block_till_done()

    assert hass.states.get(GAS_ENTITY_ID).state == STATE_UNKNOWN


async def test_mbus_meter_recreated_after_removal(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    init_integration: MockConfigEntry,
    telegrams: TelegramQueue,
    telegram: Telegram,
) -> None:
    """Test a deleted M-Bus meter gets its device and sensor back when it returns."""
    telegrams.put_nowait(Telegram())
    await hass.async_block_till_done()
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, GAS_METER_IDENTIFIER), init_integration.entry_id
    )
    assert device
    device_registry.async_remove_device(device.id)
    await hass.async_block_till_done()
    assert hass.states.get(GAS_ENTITY_ID) is None

    telegrams.put_nowait(telegram)
    await hass.async_block_till_done()

    assert hass.states.get(GAS_ENTITY_ID).state == "0.107"


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("replacement", "entity_id", "state"),
    [
        pytest.param(
            TELEGRAM_V5.replace(GAS_METER_IDENTIFIER, "3131313131"),
            GAS_ENTITY_ID,
            "0.107",
            id="mbus_same_channel",
        ),
        # Also what a different dongle on the old address of this one looks like.
        pytest.param(TELEGRAM_OTHER_METER, POWER_ENTITY_ID, "244", id="electricity"),
    ],
)
async def test_meter_replaced(
    hass: HomeAssistant,
    telegrams: TelegramQueue,
    replacement: str,
    entity_id: str,
    state: str,
) -> None:
    """Test a replacement meter gets its own sensors and never feeds the old ones."""
    telegrams.put_nowait(parse(replacement))
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_UNKNOWN
    assert hass.states.get(f"{entity_id}_2").state == state


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("pushed", "state"),
    [
        pytest.param([], "244", id="connected"),
        pytest.param([ConnectionLostError("closed")], STATE_UNAVAILABLE, id="lost"),
    ],
)
async def test_update_entity_keeps_pushed_state(
    hass: HomeAssistant,
    telegrams: TelegramQueue,
    pushed: list[Exception],
    state: str,
) -> None:
    """Test a requested update keeps the pushed state and availability."""
    for item in pushed:
        telegrams.put_nowait(item)
    await hass.async_block_till_done()
    await async_setup_component(hass, HOMEASSISTANT_DOMAIN, {})

    await hass.services.async_call(
        HOMEASSISTANT_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: POWER_ENTITY_ID},
        blocking=True,
    )

    assert hass.states.get(POWER_ENTITY_ID).state == state


@pytest.mark.parametrize(("dsmr_version", "telegram_data"), [("5B", TELEGRAM_BELGIUM)])
async def test_belgian_demand(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """Test Fluvius peak-demand registers become watt sensors."""
    average = entity_registry.async_get_entity_id(
        SENSOR_DOMAIN, DOMAIN, f"{EQUIPMENT_IDENTIFIER}_current_average_demand"
    )
    month = entity_registry.async_get_entity_id(
        SENSOR_DOMAIN, DOMAIN, f"{EQUIPMENT_IDENTIFIER}_maximum_demand_month"
    )
    assert average
    assert month
    assert hass.states.get(average).state == "1750"
    assert hass.states.get(month).state == "4326"
    assert (
        hass.states.get(average).attributes["unit_of_measurement"] == UnitOfPower.WATT
    )
    assert hass.states.get(month).attributes["unit_of_measurement"] == UnitOfPower.WATT


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("dsmr_version", "telegram_data", "state"),
    [
        pytest.param("4", TELEGRAM_V5, "0.107", id="dsmr4"),
        pytest.param("2.2", TELEGRAM_V2_2, "1.001", id="dsmr2.2"),
    ],
)
async def test_legacy_gas_meter(hass: HomeAssistant, state: str) -> None:
    """Test DSMR 4 and 2.2 gas meters get a meter reading sensor."""
    assert hass.states.get(GAS_ENTITY_ID).state == state


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("dsmr_version", "telegram_data"),
    [pytest.param("2.2", TELEGRAM_V2_2, id="dsmr2.2")],
)
async def test_identifier_without_checksum(
    hass: HomeAssistant, telegrams: TelegramQueue
) -> None:
    """Test an identifier a checksum doesn't protect can't create another meter."""
    corrupted = TELEGRAM_V2_2.replace(EQUIPMENT_IDENTIFIER, "4B38" + "0" * 28).replace(
        "0001.01*kW", "0002.02*kW"
    )
    telegrams.put_nowait(parse(corrupted, "2.2"))
    await hass.async_block_till_done()

    assert hass.states.get(POWER_ENTITY_ID).state == "2020"
    assert hass.states.get(f"{POWER_ENTITY_ID}_2") is None


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(("dsmr_version", "telegram_data"), [("Q3D", TELEGRAM_Q3D)])
async def test_power_reported_in_watts(hass: HomeAssistant) -> None:
    """Test power registers a Q3D meter reports in W are not scaled again."""
    assert hass.states.get(POWER_ENTITY_ID).state == "2125"
    assert hass.states.get("sensor.electricity_meter_power_phase_1").state == "748"


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("dsmr_version", "state"),
    [
        pytest.param("5", "high", id="netherlands"),
        pytest.param("5B", "low", id="belgium_swapped"),
    ],
)
async def test_active_tariff(hass: HomeAssistant, state: str) -> None:
    """Test tariff code 0002 maps per DSMR version."""
    assert hass.states.get(TARIFF_ENTITY_ID).state == state


@pytest.mark.usefixtures("init_integration")
async def test_unavailable_until_reconnected(
    hass: HomeAssistant, telegrams: TelegramQueue, telegram: Telegram
) -> None:
    """Test sensors go unavailable on disconnect and recover on the next telegram."""
    assert hass.states.get(POWER_ENTITY_ID).state == "244"

    with patch(
        "homeassistant.components.homey_energy_dongle.coordinator.RECONNECT_INTERVAL",
        0,
    ):
        telegrams.put_nowait(ConnectionLostError("closed"))
        await hass.async_block_till_done()
        assert hass.states.get(POWER_ENTITY_ID).state == STATE_UNAVAILABLE

        telegrams.put_nowait(telegram)
        await hass.async_block_till_done()
        assert hass.states.get(POWER_ENTITY_ID).state == "244"
