"""Test the Tado select platform."""

from collections.abc import Generator
from datetime import timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from requests import RequestException
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.components.tado import DOMAIN
from homeassistant.components.tado.const import TYPE_HEATING
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

ENTITY_ID = "select.baseboard_heater_baseboard_heater_heating_circuit"


@pytest.fixture(autouse=True)
def setup_platforms() -> Generator[None]:
    """Set up the platforms for the tests."""
    with patch("homeassistant.components.tado.PLATFORMS", [Platform.SELECT]):
        yield


@pytest.mark.usefixtures("init_integration")
async def test_entities(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, snapshot: SnapshotAssertion
) -> None:
    """Test creation of select entities."""

    config_entry: MockConfigEntry = hass.config_entries.async_entries(DOMAIN)[0]

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.parametrize(
    ("option", "expected"), [("RU5678", 2), ("no_heating_circuit", None)]
)
@pytest.mark.usefixtures("init_integration")
async def test_select_option(
    hass: HomeAssistant, option: str, expected: int | None
) -> None:
    """Test selecting an option sends the circuit number to Tado."""
    with patch(
        "PyTado.interface.api.my_tado.Tado.set_zone_heating_circuit"
    ) as mock_set_circuit:
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_OPTION: option},
            blocking=True,
        )

    mock_set_circuit.assert_called_once_with(1, expected)
    assert hass.states.get(ENTITY_ID).state == option


@pytest.mark.usefixtures("init_integration")
async def test_select_option_error(hass: HomeAssistant) -> None:
    """Test a failing assignment is reported to the user."""
    with (
        patch(
            "PyTado.interface.api.my_tado.Tado.set_zone_heating_circuit",
            side_effect=RequestException("Boom"),
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_OPTION: "RU5678"},
            blocking=True,
        )


@pytest.mark.usefixtures("init_integration")
async def test_configuration_is_read_once(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test a refresh does not read the heating circuit configuration again."""
    coordinator = hass.config_entries.async_entries(DOMAIN)[0].runtime_data

    with (
        patch(
            "PyTado.interface.api.my_tado.Tado.get_heating_circuits"
        ) as mock_circuits,
        patch("PyTado.interface.api.my_tado.Tado.get_zone_control") as mock_control,
    ):
        freezer.tick(coordinator.update_interval + timedelta(seconds=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    mock_circuits.assert_not_called()
    mock_control.assert_not_called()


@pytest.mark.usefixtures("init_integration")
async def test_failed_read_retries_the_setup(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test a failing heating circuit read makes the config entry retry."""
    with patch(
        "PyTado.interface.api.my_tado.Tado.get_heating_circuits",
        side_effect=RequestException("Boom"),
    ):
        await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("init_integration")
async def test_no_circuits_read_without_heating_zones(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test homes without a heating zone do not read the circuits at all."""
    zones = [
        zone
        for zone in hass.config_entries.async_entries(DOMAIN)[0].runtime_data.zones
        if zone["type"] != TYPE_HEATING
    ]
    with (
        patch("PyTado.interface.api.my_tado.Tado.get_zones", return_value=zones),
        patch(
            "PyTado.interface.api.my_tado.Tado.get_heating_circuits"
        ) as mock_circuits,
    ):
        await setup_integration(hass, mock_config_entry)

    mock_circuits.assert_not_called()
    assert mock_config_entry.state is ConfigEntryState.LOADED


@pytest.mark.usefixtures("init_integration")
async def test_unknown_when_circuit_is_not_listed(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the state is unknown when the assigned circuit is not in the list."""
    await hass.config_entries.async_remove(
        hass.config_entries.async_entries(DOMAIN)[0].entry_id
    )

    with patch(
        "PyTado.interface.api.my_tado.Tado.get_zone_control",
        return_value={"type": "HEATING", "heatingCircuit": 99},
    ):
        await setup_integration(hass, mock_config_entry)

    assert hass.states.get(ENTITY_ID).state == STATE_UNKNOWN
