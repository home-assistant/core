"""Test Homey Energy Dongle setup and unload."""

from unittest.mock import patch

from dsmr_parser.objects import Telegram
from homey_energy_dongle_ws import (
    ConnectionLimitError,
    ConnectionLostError,
    LocalApiDisabledError,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.homey_energy_dongle import (
    async_remove_config_entry_device,
)
from homeassistant.components.homey_energy_dongle.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)

from . import EQUIPMENT_IDENTIFIER, TELEGRAM_MBUS, TELEGRAM_V5
from .conftest import TelegramQueue

GAS_METER_IDENTIFIER = "3232323241424344313233343536373839"

REPAIR_ISSUES = [
    pytest.param(
        LocalApiDisabledError("Local API disabled"),
        "local_api_disabled",
        id="local_api",
    ),
    pytest.param(
        ConnectionLimitError("Connection limit reached"),
        "connection_limit",
        id="connection_limit",
    ),
]


async def test_setup_and_unload(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test the entry loads after the first telegram and unloads."""
    assert init_integration.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(init_integration.entry_id)
    assert init_integration.state is ConfigEntryState.NOT_LOADED


async def test_setup_retry_on_connection_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    telegrams: TelegramQueue,
) -> None:
    """Test setup is retried when the dongle can't be reached."""
    telegrams.put_nowait(ConnectionLostError("refused"))
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("telegrams")
async def test_setup_retry_without_telegram(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setup is retried when the dongle sends no telegram."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.homey_energy_dongle.coordinator.TELEGRAM_TIMEOUT", 0
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(("error", "issue_key"), REPAIR_ISSUES)
async def test_repair_issue_on_setup(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_config_entry: MockConfigEntry,
    telegrams: TelegramQueue,
    error: Exception,
    issue_key: str,
) -> None:
    """Test a user-fixable dongle rejection raises a repair issue and retries setup."""
    telegrams.put_nowait(error)
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert issue_registry.async_get_issue(
        DOMAIN, f"{issue_key}_{mock_config_entry.entry_id}"
    )


@pytest.mark.parametrize(("error", "issue_key"), REPAIR_ISSUES)
async def test_repair_issue_cleared(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    init_integration: MockConfigEntry,
    telegrams: TelegramQueue,
    telegram: Telegram,
    error: Exception,
    issue_key: str,
) -> None:
    """Test the repair issue is removed once telegrams arrive again."""
    issue_id = f"{issue_key}_{init_integration.entry_id}"

    with patch(
        "homeassistant.components.homey_energy_dongle.coordinator.RECONNECT_INTERVAL",
        0,
    ):
        telegrams.put_nowait(error)
        await hass.async_block_till_done()
        assert issue_registry.async_get_issue(DOMAIN, issue_id)

        telegrams.put_nowait(telegram)
        await hass.async_block_till_done()
        assert not issue_registry.async_get_issue(DOMAIN, issue_id)


@pytest.mark.parametrize(
    ("identifier", "pushed", "removable"),
    [
        pytest.param(GAS_METER_IDENTIFIER, [], False, id="meter_present"),
        pytest.param(GAS_METER_IDENTIFIER, [Telegram()], True, id="meter_missing"),
        pytest.param(EQUIPMENT_IDENTIFIER, [Telegram()], False, id="electricity_meter"),
    ],
)
async def test_remove_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    init_integration: MockConfigEntry,
    telegrams: TelegramQueue,
    identifier: str,
    pushed: list[Telegram],
    removable: bool,
) -> None:
    """Test only M-Bus meters missing from the telegram can be removed."""
    for telegram in pushed:
        telegrams.put_nowait(telegram)
    await hass.async_block_till_done()
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, identifier), init_integration.entry_id
    )
    assert device

    assert (
        await async_remove_config_entry_device(hass, init_integration, device)
        is removable
    )


@pytest.mark.parametrize(
    ("identifier", "removable"),
    [
        pytest.param(GAS_METER_IDENTIFIER, True, id="mbus_meter"),
        pytest.param(EQUIPMENT_IDENTIFIER, False, id="electricity_meter"),
    ],
)
async def test_remove_device_unloaded(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    init_integration: MockConfigEntry,
    identifier: str,
    removable: bool,
) -> None:
    """Test M-Bus meters can be removed while the entry is unloaded."""
    await hass.config_entries.async_unload(init_integration.entry_id)
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, identifier), init_integration.entry_id
    )
    assert device

    assert (
        await async_remove_config_entry_device(hass, init_integration, device)
        is removable
    )


@pytest.mark.parametrize(
    ("telegram_data", "identifier", "serial_number"),
    [
        pytest.param(
            TELEGRAM_V5,
            EQUIPMENT_IDENTIFIER,
            EQUIPMENT_IDENTIFIER,
            id="electricity",
        ),
        pytest.param(
            TELEGRAM_V5,
            GAS_METER_IDENTIFIER,
            GAS_METER_IDENTIFIER,
            id="gas",
        ),
        pytest.param(
            TELEGRAM_MBUS,
            f"{EQUIPMENT_IDENTIFIER}_mbus3",
            None,
            id="water_without_identifier",
        ),
    ],
)
async def test_meter_serial_number(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    init_integration: MockConfigEntry,
    identifier: str,
    serial_number: str | None,
) -> None:
    """Test a reported meter identifier is the device serial number."""
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, identifier), init_integration.entry_id
    )
    assert device
    assert device.serial_number == serial_number


async def test_dongle_has_no_entities(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """Test the dongle is only the parent of the meters."""
    dongle = device_registry.async_get_device_by_identifier(
        (DOMAIN, init_integration.entry_id), init_integration.entry_id
    )
    electricity = device_registry.async_get_device_by_identifier(
        (DOMAIN, EQUIPMENT_IDENTIFIER), init_integration.entry_id
    )
    assert dongle
    assert electricity
    assert electricity.via_device_id == dongle.id
    assert not er.async_entries_for_device(
        entity_registry, dongle.id, include_disabled_entities=True
    )
    assert not await async_remove_config_entry_device(hass, init_integration, dongle)
