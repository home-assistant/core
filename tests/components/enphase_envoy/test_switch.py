"""Test Enphase Envoy number sensors."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, Mock, patch

from pyenphase import Envoy, EnvoyTokenAuth
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.enphase_envoy import DOMAIN
from homeassistant.components.enphase_envoy.const import Platform
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from . import load_envoy_fixture

from tests.common import MockConfigEntry

SWITCH_FIXTURES = (
    [
        pytest.param("envoy_metered_batt_relay", 5, id="envoy_metered_batt_relay"),
    ],
)


@pytest.fixture(name="setup_enphase_envoy_switch")
async def setup_enphase_envoy_sensor_fixture(
    hass: HomeAssistant, config: dict[str, str], switch_envoy: AsyncMock
) -> AsyncGenerator[None, None]:
    """Define a fixture to set up Enphase Envoy with number platform only."""
    with (
        patch(
            "homeassistant.components.enphase_envoy.config_flow.Envoy",
            return_value=switch_envoy,
        ),
        patch(
            "homeassistant.components.enphase_envoy.Envoy",
            return_value=switch_envoy,
        ),
        patch(
            "homeassistant.components.enphase_envoy.PLATFORMS",
            [Platform.SWITCH],
        ),
    ):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
        yield


@pytest.mark.parametrize(
    ("switch_envoy", "entity_count"), *SWITCH_FIXTURES, indirect=["switch_envoy"]
)
async def test_switch(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    setup_enphase_envoy_switch: None,
    mock_set_reserve_soc: AsyncMock,
    switch_envoy: AsyncMock,
    entity_count: int,
) -> None:
    """Test enphase_envoy switch entities operation."""

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
    ("switch_envoy", "entity_count"), *SWITCH_FIXTURES, indirect=["switch_envoy"]
)
async def test_switch_operation(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    setup_enphase_envoy_switch: None,
    mock_go_on_grid: AsyncMock,
    mock_go_off_grid: AsyncMock,
    switch_envoy: AsyncMock,
    entity_count: int,
) -> None:
    """Test enphase_envoy number entities operation."""

    assert len(hass.states.async_all()) == entity_count

    entity_base = f"{Platform.NUMBER}.enpower_"

    sn = switch_envoy.data.enpower.serial_number

    # build switching orders
    INITIAL_OFF_ORDER = (SERVICE_TURN_ON, SERVICE_TURN_OFF, SERVICE_TOGGLE)
    INITIAL_ON_ORDER = (SERVICE_TURN_OFF, SERVICE_TURN_ON, SERVICE_TOGGLE)

    entity_base = f"{Platform.SWITCH}.enpower_"

    sn = switch_envoy.data.enpower.serial_number
    test_entity = f"{entity_base}{sn}_grid_enabled"
    grid_status = (
        STATE_ON
        if (switch_envoy.data.enpower.mains_admin_state == "closed")
        else STATE_OFF
    )
    # validate envoy value is reflected in entity
    assert grid_status == hass.states.get(test_entity).state

    # test grid status switch change operation
    for option in INITIAL_OFF_ORDER if grid_status == STATE_OFF else INITIAL_ON_ORDER:
        await hass.services.async_call(
            Platform.SWITCH,
            option,
            {ATTR_ENTITY_ID: test_entity},
            blocking=True,
        )
    assert mock_go_on_grid.await_count == (2 if grid_status == STATE_OFF else 1)
    assert mock_go_off_grid.await_count == (2 if grid_status == STATE_ON else 1)


@pytest.fixture(name="switch_envoy")
async def mock_switch_envoy_fixture(
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
