"""Test Enphase Envoy binary sensors."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, Mock, patch

from pyenphase import Envoy, EnvoyTokenAuth
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.enphase_envoy import DOMAIN
from homeassistant.components.enphase_envoy.const import Platform
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from . import load_envoy_fixture

from tests.common import MockConfigEntry

BINARY_FIXTURES = (
    [
        pytest.param("envoy_metered_batt_relay", 4, id="envoy_metered_batt_relay"),
    ],
)


@pytest.fixture(name="setup_enphase_envoy_binary")
async def setup_enphase_envoy_binary_fixture(
    hass: HomeAssistant, config: dict[str, str], binary_envoy: AsyncMock
) -> AsyncGenerator[None, None]:
    """Define a fixture to set up Enphase Envoy with binary sensor platform only."""
    with (
        patch(
            "homeassistant.components.enphase_envoy.config_flow.Envoy",
            return_value=binary_envoy,
        ),
        patch(
            "homeassistant.components.enphase_envoy.Envoy",
            return_value=binary_envoy,
        ),
        patch(
            "homeassistant.components.enphase_envoy.PLATFORMS",
            [Platform.BINARY_SENSOR],
        ),
    ):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
        yield


@pytest.mark.parametrize(
    ("binary_envoy", "entity_count"), *BINARY_FIXTURES, indirect=["binary_envoy"]
)
async def test_binary_sensor(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    setup_enphase_envoy_binary: None,
    binary_envoy: AsyncMock,
    entity_registry: er.EntityRegistry,
    entity_count: int,
) -> None:
    """Test enphase_envoy binary_sensor entities."""

    # number entities states should be created from test data
    assert len(hass.states.async_all()) == entity_count

    entity_entries = er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )

    assert len(entity_entries) == entity_count

    # compare registered entities against snapshot of prior run
    for entity_entry in entity_entries:
        assert entity_entry == snapshot(name=f"{entity_entry.entity_id}-entry")
        assert hass.states.get(entity_entry.entity_id) == snapshot(
            name=f"{entity_entry.entity_id}-state"
        )


@pytest.mark.parametrize(
    ("binary_envoy", "entity_count"), *BINARY_FIXTURES, indirect=["binary_envoy"]
)
async def test_binary_sensor_data(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    setup_enphase_envoy_binary: None,
    binary_envoy: AsyncMock,
    entity_registry: er.EntityRegistry,
    entity_count: int,
) -> None:
    """Test enphase_envoy encharge enpower entities values and names."""

    assert len(hass.states.async_all()) == entity_count

    entity_entries = er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )

    entity_status = {}
    for entity_entry in entity_entries:
        entity_status[entity_entry.entity_id] = entity_entry.disabled_by

    entity_base = f"{Platform.BINARY_SENSOR}.enpower_"

    sn = binary_envoy.data.enpower.serial_number
    assert (entity_state := hass.states.get(f"{entity_base}{sn}_communicating"))
    assert (
        entity_state.state == STATE_ON
        if binary_envoy.data.enpower.communicating
        else STATE_OFF
    )
    assert (entity_state := hass.states.get(f"{entity_base}{sn}_grid_status"))
    assert (
        entity_state.state == STATE_ON
        if binary_envoy.data.enpower.mains_oper_state == "closed"
        else STATE_OFF
    )

    entity_base = "binary_sensor.encharge_"

    # these should be defined and have value from data
    for sn, encharge_inventory in binary_envoy.data.encharge_inventory.items():
        assert (entity_state := hass.states.get(f"{entity_base}{sn}_communicating"))
        assert (
            entity_state.state == STATE_ON
            if encharge_inventory.communicating
            else STATE_OFF
        )
        assert (entity_state := hass.states.get(f"{entity_base}{sn}_dc_switch"))
        assert (
            entity_state.state == STATE_ON
            if encharge_inventory.dc_switch_off
            else STATE_OFF
        )


@pytest.fixture(name="binary_envoy")
async def mock_binary_envoy_fixture(
    serial_number: str,
    mock_authenticate: AsyncMock,
    mock_setup: AsyncMock,
    mock_auth: EnvoyTokenAuth,
    mock_go_on_grid: AsyncMock,
    mock_go_off_grid: AsyncMock,
    mock_open_dry_contact: AsyncMock,
    mock_close_dry_contact: AsyncMock,
    mock_update_dry_contact: AsyncMock,
    mock_disable_charge_from_grid: AsyncMock,
    mock_enable_charge_from_grid: AsyncMock,
    mock_set_reserve_soc: AsyncMock,
    mock_set_storage_mode: AsyncMock,
    request: pytest.FixtureRequest,
) -> AsyncGenerator[AsyncMock, None]:
    """Define a mocked Envoy fixture."""
    mock_envoy = Mock(spec=Envoy)
    with (
        patch(
            "homeassistant.components.enphase_envoy.config_flow.Envoy",
            return_value=mock_envoy,
        ),
        patch(
            "homeassistant.components.enphase_envoy.Envoy",
            return_value=mock_envoy,
        ),
    ):
        # load the fixture
        load_envoy_fixture(mock_envoy, request.param)

        # set the mock for the methods
        mock_envoy.serial_number = serial_number
        mock_envoy.authenticate = mock_authenticate
        mock_envoy.go_off_grid = mock_go_off_grid
        mock_envoy.go_on_grid = mock_go_on_grid
        mock_envoy.open_dry_contact = mock_open_dry_contact
        mock_envoy.close_dry_contact = mock_close_dry_contact
        mock_envoy.disable_charge_from_grid = mock_disable_charge_from_grid
        mock_envoy.enable_charge_from_grid = mock_enable_charge_from_grid
        mock_envoy.update_dry_contact = mock_update_dry_contact
        mock_envoy.set_reserve_soc = mock_set_reserve_soc
        mock_envoy.set_storage_mode = mock_set_storage_mode
        mock_envoy.setup = mock_setup
        mock_envoy.auth = mock_auth
        mock_envoy.update = AsyncMock(return_value=mock_envoy.data)

        return mock_envoy
