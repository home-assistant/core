"""Test Homey Energy Dongle sensors."""

from unittest.mock import patch

from dsmr_parser import telegram_specifications
from dsmr_parser.objects import Telegram
from dsmr_parser.parsers import TelegramParser
from homey_energy_dongle_ws import ConnectionLostError, parse_telegram
from homey_energy_dongle_ws.parser import TELEGRAM_SPECIFICATIONS
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.homeassistant import (
    DOMAIN as HOMEASSISTANT_DOMAIN,
    SERVICE_UPDATE_ENTITY,
)
from homeassistant.components.homey_energy_dongle.const import CONF_DSMR_VERSION, DOMAIN
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

from . import EQUIPMENT_IDENTIFIER, TELEGRAM_MBUS, TELEGRAM_Q3D, TELEGRAM_V5
from .conftest import TelegramQueue

POWER_ENTITY_ID = "sensor.electricity_meter_power"
TARIFF_ENTITY_ID = "sensor.electricity_meter_active_tariff"
GAS_ENTITY_ID = "sensor.gas_meter_meter_reading"


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
    parser = TelegramParser(telegram_specifications.V5, apply_checksum_validation=False)

    telegrams.put_nowait(parser.parse(TELEGRAM_V5))
    await hass.async_block_till_done()

    assert hass.states.get(GAS_ENTITY_ID).state == "0.107"


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
        (DOMAIN, "3232323241424344313233343536373839"), init_integration.entry_id
    )
    assert device
    device_registry.async_remove_device(device.id)
    await hass.async_block_till_done()
    assert hass.states.get(GAS_ENTITY_ID) is None

    telegrams.put_nowait(telegram)
    await hass.async_block_till_done()

    assert hass.states.get(GAS_ENTITY_ID).state == "0.107"


@pytest.mark.usefixtures("init_integration")
async def test_mbus_meter_replaced_on_same_channel(
    hass: HomeAssistant, telegrams: TelegramQueue
) -> None:
    """Test a replacement meter on the same channel does not feed the old sensor."""
    parser = TelegramParser(telegram_specifications.V5, apply_checksum_validation=False)
    telegrams.put_nowait(
        parser.parse(
            TELEGRAM_V5.replace("3232323241424344313233343536373839", "3131313131")
        )
    )
    await hass.async_block_till_done()

    assert hass.states.get(GAS_ENTITY_ID).state == STATE_UNKNOWN
    assert hass.states.get(f"{GAS_ENTITY_ID}_2").state == "0.107"


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


def _belgium_telegram() -> str:
    """Return a DSMR 5 telegram with the Fluvius demand registers."""
    body = TELEGRAM_V5[: TELEGRAM_V5.rindex("!")]
    body += "1-0:1.4.0(01.750*kW)\r\n1-0:1.6.0(170102120000W)(04.326*kW)\r\n!"
    return f"{body}{TelegramParser.crc16(body):04X}\r\n"


async def test_belgian_demand(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    telegrams: TelegramQueue,
) -> None:
    """Test Fluvius peak-demand registers become watt sensors."""
    parser = TelegramParser(
        telegram_specifications.BELGIUM_FLUVIUS, apply_checksum_validation=False
    )
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        data={**mock_config_entry.data, CONF_DSMR_VERSION: "5B"},
    )
    telegrams.put_nowait(parser.parse(_belgium_telegram()))
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

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


async def test_power_reported_in_watts(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    telegrams: TelegramQueue,
) -> None:
    """Test power registers a Q3D meter reports in W are not scaled again."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        data={**mock_config_entry.data, CONF_DSMR_VERSION: "Q3D"},
    )
    telegrams.put_nowait(
        parse_telegram(
            TELEGRAM_Q3D, telegram_specification=TELEGRAM_SPECIFICATIONS["Q3D"]
        )
    )
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(POWER_ENTITY_ID).state == "2125"
    assert hass.states.get("sensor.electricity_meter_power_phase_1").state == "748"


@pytest.mark.parametrize(
    ("dsmr_version", "state"),
    [
        pytest.param("5", "high", id="netherlands"),
        pytest.param("5B", "low", id="belgium_swapped"),
    ],
)
async def test_active_tariff(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    telegrams: TelegramQueue,
    telegram: Telegram,
    dsmr_version: str,
    state: str,
) -> None:
    """Test tariff code 0002 maps per DSMR version."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        data={**mock_config_entry.data, CONF_DSMR_VERSION: dsmr_version},
    )
    telegrams.put_nowait(telegram)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

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
