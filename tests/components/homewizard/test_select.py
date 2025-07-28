"""Test the Select entity for HomeWizard."""

from unittest.mock import MagicMock

from homewizard_energy import UnsupportedError
from homewizard_energy.errors import RequestError, UnauthorizedError
from homewizard_energy.models import Batteries
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.homewizard.const import UPDATE_INTERVAL
from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util

from tests.common import async_fire_time_changed

pytestmark = [
    pytest.mark.usefixtures("init_integration"),
]


@pytest.mark.parametrize(
    ("device_fixture", "entity_ids"),
    [
        (
            "HWE-WTR",
            [
                "select.device_battery_group_mode",
            ],
        ),
        (
            "SDM230",
            [
                "select.device_battery_group_mode",
            ],
        ),
        (
            "SDM630",
            [
                "select.device_battery_group_mode",
            ],
        ),
        (
            "HWE-KWH1",
            [
                "select.device_battery_group_mode",
            ],
        ),
        (
            "HWE-KWH3",
            [
                "select.device_battery_group_mode",
            ],
        ),
    ],
)
async def test_entities_not_created_for_device(
    hass: HomeAssistant,
    entity_ids: list[str],
) -> None:
    """Ensures entities for a specific device are not created."""
    for entity_id in entity_ids:
        assert not hass.states.get(entity_id)


@pytest.mark.parametrize(
    ("device_fixture", "entity_id"),
    [
        ("HWE-P1", "select.device_battery_group_mode"),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_select_entity_snapshots(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    entity_id: str,
) -> None:
    """Test that select entity state and registry entries match snapshots."""
    assert (state := hass.states.get(entity_id))
    assert snapshot == state

    assert (entity_entry := entity_registry.async_get(entity_id))
    assert snapshot == entity_entry

    assert entity_entry.device_id
    assert (device_entry := device_registry.async_get(entity_entry.device_id))
    assert snapshot == device_entry


@pytest.mark.parametrize(
    ("device_fixture", "entity_id", "option", "expected_mode"),
    [
        (
            "HWE-P1",
            "select.device_battery_group_mode",
            "standby",
            Batteries.Mode.STANDBY,
        ),
        (
            "HWE-P1",
            "select.device_battery_group_mode",
            "to_full",
            Batteries.Mode.TO_FULL,
        ),
        ("HWE-P1", "select.device_battery_group_mode", "zero", Batteries.Mode.ZERO),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_select_set_option(
    hass: HomeAssistant,
    mock_homewizardenergy: MagicMock,
    entity_id: str,
    option: str,
    expected_mode: Batteries.Mode,
) -> None:
    """Test that selecting an option calls the correct API method."""
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_OPTION: option,
        },
        blocking=True,
    )
    mock_homewizardenergy.batteries.assert_called_with(mode=expected_mode)


@pytest.mark.parametrize(
    ("device_fixture", "entity_id", "option"),
    [
        ("HWE-P1", "select.device_battery_group_mode", "zero"),
        ("HWE-P1", "select.device_battery_group_mode", "standby"),
        ("HWE-P1", "select.device_battery_group_mode", "to_full"),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_select_request_error(
    hass: HomeAssistant,
    mock_homewizardenergy: MagicMock,
    entity_id: str,
    option: str,
) -> None:
    """Test that RequestError is handled and raises HomeAssistantError."""
    mock_homewizardenergy.batteries.side_effect = RequestError
    with pytest.raises(
        HomeAssistantError,
        match=r"^An error occurred while communicating with your HomeWizard Energy device$",
    ):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: entity_id,
                ATTR_OPTION: option,
            },
            blocking=True,
        )


@pytest.mark.parametrize(
    ("device_fixture", "entity_id", "option"),
    [
        ("HWE-P1", "select.device_battery_group_mode", "to_full"),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_select_unauthorized_error(
    hass: HomeAssistant,
    mock_homewizardenergy: MagicMock,
    entity_id: str,
    option: str,
) -> None:
    """Test that UnauthorizedError is handled and raises HomeAssistantError."""
    mock_homewizardenergy.batteries.side_effect = UnauthorizedError
    with pytest.raises(
        HomeAssistantError,
        match=r"^The local API is unauthorized\. Restore API access by following the instructions in the repair issue$",
    ):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: entity_id,
                ATTR_OPTION: option,
            },
            blocking=True,
        )


@pytest.mark.parametrize("device_fixture", ["HWE-P1"])
@pytest.mark.parametrize("exception", [RequestError, UnsupportedError])
@pytest.mark.parametrize(
    ("entity_id", "method"),
    [
        ("select.device_battery_group_mode", "combined"),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_select_unreachable(
    hass: HomeAssistant,
    mock_homewizardenergy: MagicMock,
    exception: Exception,
    entity_id: str,
    method: str,
) -> None:
    """Test that unreachable devices are marked as unavailable."""
    mocked_method = getattr(mock_homewizardenergy, method)
    mocked_method.side_effect = exception
    async_fire_time_changed(hass, dt_util.utcnow() + UPDATE_INTERVAL)
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("device_fixture", "entity_id"),
    [
        ("HWE-P1", "select.device_battery_group_mode"),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_select_multiple_state_changes(
    hass: HomeAssistant,
    mock_homewizardenergy: MagicMock,
    entity_id: str,
) -> None:
    """Test changing select state multiple times in sequence."""
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_OPTION: "zero",
        },
        blocking=True,
    )
    mock_homewizardenergy.batteries.assert_called_with(mode=Batteries.Mode.ZERO)

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_OPTION: "to_full",
        },
        blocking=True,
    )
    mock_homewizardenergy.batteries.assert_called_with(mode=Batteries.Mode.TO_FULL)

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_OPTION: "standby",
        },
        blocking=True,
    )
    mock_homewizardenergy.batteries.assert_called_with(mode=Batteries.Mode.STANDBY)


@pytest.mark.parametrize(
    ("device_fixture", "entity_ids"),
    [
        (
            "HWE-P1",
            [
                "select.device_battery_group_mode",
            ],
        ),
    ],
)
async def test_disabled_by_default_selects(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, entity_ids: list[str]
) -> None:
    """Test the disabled by default selects."""
    for entity_id in entity_ids:
        assert not hass.states.get(entity_id)

        assert (entry := entity_registry.async_get(entity_id))
        assert entry.disabled
        assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
