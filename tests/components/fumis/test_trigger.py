"""Tests for the Fumis triggers."""

from dataclasses import replace
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from fumis import FumisConnectionError, FumisInfo
import probatio
import pytest

from homeassistant.components import automation
from homeassistant.components.fumis.const import DOMAIN, SCAN_INTERVAL
from homeassistant.components.fumis.trigger import FuelBecameLowTrigger
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from .const import UNIQUE_ID

from tests.common import MockConfigEntry, async_fire_time_changed

NO_ALERT = 0
LOW_FUEL = 1
DOOR_OPEN = 6
UNRECOGNIZED_ALERT = 99
UPDATE_FAILED = FumisConnectionError("Connection lost")


def _info_with_alert(info: FumisInfo, alert: int) -> FumisInfo:
    """Return the stove info with the given raw alert code."""
    return replace(info, controller=replace(info.controller, alert=alert))


def _updates(
    info: FumisInfo, steps: list[int | Exception]
) -> list[FumisInfo | Exception]:
    """Return the update results for a sequence of alert codes and failures."""
    return [
        step if isinstance(step, Exception) else _info_with_alert(info, step)
        for step in steps
    ]


async def _async_setup_automation(hass: HomeAssistant, device_id: str) -> None:
    """Set up an automation using the fuel became low trigger."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "trigger": f"{DOMAIN}.fuel_became_low",
                    "options": {"device_id": device_id},
                },
                "action": {
                    "action": "test.automation",
                    "data": {
                        "device_id": "{{ trigger.device_id }}",
                        "description": "{{ trigger.description }}",
                    },
                },
            }
        },
    )


async def _async_poll(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Let the coordinator poll the stove once."""
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("steps", "expected_calls"),
    [
        pytest.param([NO_ALERT, LOW_FUEL], 1, id="became_low"),
        pytest.param(
            [NO_ALERT, DOOR_OPEN, LOW_FUEL],
            1,
            id="through_other_alert",
        ),
        pytest.param(
            [NO_ALERT, LOW_FUEL, NO_ALERT, LOW_FUEL],
            2,
            id="twice",
        ),
        pytest.param([LOW_FUEL, LOW_FUEL], 0, id="stays"),
        pytest.param(
            [LOW_FUEL, DOOR_OPEN, LOW_FUEL],
            0,
            id="hidden_by_other_alert",
        ),
        pytest.param(
            [DOOR_OPEN, LOW_FUEL],
            0,
            id="after_other_alert_only",
        ),
        pytest.param([NO_ALERT, DOOR_OPEN], 0, id="other_alert"),
        pytest.param(
            [NO_ALERT, UPDATE_FAILED, LOW_FUEL],
            0,
            id="after_update_failed",
        ),
        pytest.param(
            [NO_ALERT, UNRECOGNIZED_ALERT, LOW_FUEL],
            0,
            id="after_unrecognized_alert",
        ),
    ],
)
async def test_trigger(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_fumis: MagicMock,
    service_calls: list[ServiceCall],
    steps: list[int | Exception],
    expected_calls: int,
) -> None:
    """Test the trigger fires when the low fuel alert becomes active."""
    mock_fumis.update_info.side_effect = _updates(
        mock_fumis.update_info.return_value, steps
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, UNIQUE_ID), mock_config_entry.entry_id
    )
    assert device
    await _async_setup_automation(hass, device.id)

    for _ in steps[1:]:
        await _async_poll(hass, freezer)

    assert [call.data for call in service_calls] == [
        {"device_id": device.id, "description": f"fuel became low on {device.name}"}
    ] * expected_calls


@pytest.mark.usefixtures("init_integration")
async def test_trigger_after_reload(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_fumis: MagicMock,
    service_calls: list[ServiceCall],
) -> None:
    """Test a reload starts over, and the trigger keeps working after it."""
    info = mock_fumis.update_info.return_value
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, UNIQUE_ID), mock_config_entry.entry_id
    )
    assert device
    await _async_setup_automation(hass, device.id)

    mock_fumis.update_info.return_value = _info_with_alert(info, LOW_FUEL)
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert not service_calls

    mock_fumis.update_info.return_value = _info_with_alert(info, NO_ALERT)
    await _async_poll(hass, freezer)
    mock_fumis.update_info.return_value = _info_with_alert(info, LOW_FUEL)
    await _async_poll(hass, freezer)

    assert len(service_calls) == 1


async def test_trigger_before_stove_loaded(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_fumis: MagicMock,
    service_calls: list[ServiceCall],
) -> None:
    """Test the first update of a stove that loads later is not compared."""
    mock_fumis.update_info.side_effect = _updates(
        mock_fumis.update_info.return_value, [LOW_FUEL, NO_ALERT, LOW_FUEL]
    )
    mock_config_entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, UNIQUE_ID)},
    )
    await _async_setup_automation(hass, device.id)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert not service_calls

    await _async_poll(hass, freezer)
    await _async_poll(hass, freezer)

    assert len(service_calls) == 1


async def test_trigger_without_entities(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_fumis: MagicMock,
    service_calls: list[ServiceCall],
) -> None:
    """Test the trigger keeps the stove polling when no entity listens to it."""
    info = mock_fumis.update_info.return_value
    mock_config_entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, UNIQUE_ID)},
    )

    with patch("homeassistant.components.fumis.PLATFORMS", []):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        await _async_setup_automation(hass, device.id)

        mock_fumis.update_info.return_value = _info_with_alert(info, LOW_FUEL)
        await _async_poll(hass, freezer)

        assert len(service_calls) == 1

        await hass.config_entries.async_reload(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        mock_fumis.update_info.return_value = _info_with_alert(info, NO_ALERT)
        await _async_poll(hass, freezer)
        mock_fumis.update_info.return_value = _info_with_alert(info, LOW_FUEL)
        await _async_poll(hass, freezer)

        assert len(service_calls) == 2

        await hass.services.async_call(
            automation.DOMAIN, "turn_off", {"entity_id": "all"}, blocking=True
        )
        polls = mock_fumis.update_info.call_count
        await _async_poll(hass, freezer)

        assert mock_fumis.update_info.call_count == polls


@pytest.mark.usefixtures("init_integration")
async def test_trigger_detached(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_fumis: MagicMock,
    service_calls: list[ServiceCall],
) -> None:
    """Test the trigger stops listening when the automation is turned off."""
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, UNIQUE_ID), mock_config_entry.entry_id
    )
    assert device
    await _async_setup_automation(hass, device.id)

    await hass.services.async_call(
        automation.DOMAIN, "turn_off", {"entity_id": "all"}, blocking=True
    )
    service_calls.clear()

    mock_fumis.update_info.return_value = _info_with_alert(
        mock_fumis.update_info.return_value, LOW_FUEL
    )
    await _async_poll(hass, freezer)

    assert not service_calls


@pytest.mark.usefixtures("init_integration")
async def test_trigger_device_removed(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_fumis: MagicMock,
    service_calls: list[ServiceCall],
) -> None:
    """Test a stove removed while the automation was off is skipped."""
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, UNIQUE_ID), mock_config_entry.entry_id
    )
    assert device
    await _async_setup_automation(hass, device.id)

    await hass.services.async_call(
        automation.DOMAIN, "turn_off", {"entity_id": "all"}, blocking=True
    )
    device_registry.async_remove_device(device.id)
    await hass.services.async_call(
        automation.DOMAIN, "turn_on", {"entity_id": "all"}, blocking=True
    )
    service_calls.clear()

    mock_fumis.update_info.return_value = _info_with_alert(
        mock_fumis.update_info.return_value, LOW_FUEL
    )
    await _async_poll(hass, freezer)

    assert not service_calls


async def test_trigger_invalid_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the trigger only accepts Fumis devices."""
    other_entry = MockConfigEntry(domain="other")
    other_entry.add_to_hass(hass)
    other_device = device_registry.async_get_or_create(
        config_entry_id=other_entry.entry_id,
        identifiers={("other", "device")},
    )

    with pytest.raises(probatio.Invalid, match="is not a Fumis stove"):
        await FuelBecameLowTrigger.async_validate_complete_config(
            hass,
            {
                "platform": f"{DOMAIN}.fuel_became_low",
                "options": {"device_id": "missing"},
            },
        )

    with pytest.raises(probatio.Invalid, match="is not a Fumis stove"):
        await FuelBecameLowTrigger.async_validate_complete_config(
            hass,
            {
                "platform": f"{DOMAIN}.fuel_became_low",
                "options": {"device_id": other_device.id},
            },
        )
