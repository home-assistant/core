"""Test Enphase Envoy select."""

from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

from pyenphase import Envoy, EnvoyTokenAuth
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.enphase_envoy import DOMAIN
from homeassistant.components.enphase_envoy.const import Platform
from homeassistant.components.enphase_envoy.select import (
    ACTION_OPTIONS,
    MODE_OPTIONS,
    RELAY_ACTION_MAP,
    RELAY_MODE_MAP,
    REVERSE_RELAY_ACTION_MAP,
    REVERSE_RELAY_MODE_MAP,
    REVERSE_STORAGE_MODE_MAP,
    STORAGE_MODE_MAP,
    STORAGE_MODE_OPTIONS,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from . import load_envoy_fixture

from tests.common import MockConfigEntry

SELECT_STORAGE_FIXTURES = (
    [
        pytest.param("envoy_metered_batt_relay", 13, id="envoy_metered_batt_relay"),
    ],
)
SELECT_FIXTURES = (
    [
        pytest.param("envoy", 0, id="envoy"),
        pytest.param("envoy_metered_batt_relay", 13, id="envoy_metered_batt_relay"),
        pytest.param("envoy_nobatt_metered_3p", 0, id="envoy_nobatt_metered_3p"),
        pytest.param("envoy_1p_metered", 0, id="envoy_1p_metered"),
        pytest.param("envoy_tot_cons_metered", 0, id="envoy_tot_cons_metered"),
    ],
)


@pytest.fixture(name="setup_enphase_envoy_select")
async def setup_enphase_envoy_select_fixture(
    hass: HomeAssistant, config: dict[str, str], select_envoy: AsyncMock
) -> AsyncGenerator[None, None]:
    """Define a fixture to set up Enphase Envoy with number platform only."""
    with (
        patch(
            "homeassistant.components.enphase_envoy.config_flow.Envoy",
            return_value=select_envoy,
        ),
        patch(
            "homeassistant.components.enphase_envoy.Envoy",
            return_value=select_envoy,
        ),
        patch(
            "homeassistant.components.enphase_envoy.PLATFORMS",
            [Platform.SELECT],
        ),
    ):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
        yield


@pytest.mark.parametrize(
    ("select_envoy", "entity_count"), *SELECT_FIXTURES, indirect=["select_envoy"]
)
async def test_select(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    setup_enphase_envoy_select: None,
    select_envoy: AsyncMock,
    entity_registry: er.EntityRegistry,
    entity_count: int,
) -> None:
    """Test enphase_envoy select entities."""

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
    ("select_envoy", "entity_count"), *SELECT_FIXTURES, indirect=["select_envoy"]
)
async def test_select_relay_actions(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    setup_enphase_envoy_select: None,
    select_envoy: AsyncMock,
    mock_update_dry_contact: AsyncMock,
    entity_count: int,
) -> None:
    """Test enphase_envoy select relay entities actions."""

    assert len(hass.states.async_all()) == entity_count

    entity_base = f"{Platform.SELECT}."

    for contact_id, dry_contact in select_envoy.data.dry_contact_settings.items():
        name = dry_contact.load_name.lower().replace(" ", "_")
        targets: list[Any] = []
        targets.extend(
            (
                ("generator_action", dry_contact.generator_action),
                ("microgrid_action", dry_contact.micro_grid_action),
                ("grid_action", dry_contact.grid_action),
            )
        )
        for target in targets:
            test_entity = f"{entity_base}{name}_{target[0]}"
            assert (entity_state := hass.states.get(test_entity))
            assert RELAY_ACTION_MAP[target[1]] == (current_state := entity_state.state)
            for mode in [mode for mode in ACTION_OPTIONS if not current_state]:
                await hass.services.async_call(
                    Platform.SELECT,
                    "select_option",
                    {
                        ATTR_ENTITY_ID: test_entity,
                        "option": mode,
                    },
                    blocking=True,
                )
                mock_update_dry_contact.assert_awaited_once()
                mock_update_dry_contact.assert_called_with(
                    {"id": contact_id, target[0]: REVERSE_RELAY_ACTION_MAP[mode]}
                )
                mock_update_dry_contact.reset_mock()


@pytest.mark.parametrize(
    ("select_envoy", "entity_count"), *SELECT_FIXTURES, indirect=["select_envoy"]
)
async def test_select_relay_modes(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    setup_enphase_envoy_select: None,
    select_envoy: AsyncMock,
    mock_update_dry_contact: AsyncMock,
    entity_count: int,
) -> None:
    """Test enphase_envoy select relay entities modes."""

    assert len(hass.states.async_all()) == entity_count

    entity_base = f"{Platform.SELECT}."

    for contact_id, dry_contact in select_envoy.data.dry_contact_settings.items():
        name = dry_contact.load_name.lower().replace(" ", "_")
        test_entity = f"{entity_base}{name}_mode"
        assert (entity_state := hass.states.get(test_entity))
        assert RELAY_MODE_MAP[dry_contact.mode] == (current_state := entity_state.state)
        for mode in [mode for mode in MODE_OPTIONS if not current_state]:
            await hass.services.async_call(
                Platform.SELECT,
                "select_option",
                {
                    ATTR_ENTITY_ID: test_entity,
                    "option": mode,
                },
                blocking=True,
            )
            mock_update_dry_contact.assert_awaited_once()
            mock_update_dry_contact.assert_called_with(
                {"id": contact_id, "mode": REVERSE_RELAY_MODE_MAP[mode]}
            )
            mock_update_dry_contact.reset_mock()


@pytest.mark.parametrize(
    ("select_envoy", "entity_count"),
    *SELECT_STORAGE_FIXTURES,
    indirect=["select_envoy"],
)
async def test_select_storage_modes(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    setup_enphase_envoy_select: None,
    select_envoy: AsyncMock,
    mock_set_storage_mode: AsyncMock,
    entity_count: int,
) -> None:
    """Test enphase_envoy select entities storage modes."""

    assert len(hass.states.async_all()) == entity_count

    entity_base = f"{Platform.SELECT}.enpower_"

    sn = select_envoy.data.enpower.serial_number
    test_entity = f"{entity_base}{sn}_storage_mode"
    assert (entity_state := hass.states.get(test_entity))
    assert STORAGE_MODE_MAP[select_envoy.data.tariff.storage_settings.mode] == (
        current_state := entity_state.state
    )

    for mode in [mode for mode in STORAGE_MODE_OPTIONS if not current_state]:
        await hass.services.async_call(
            Platform.SELECT,
            "select_option",
            {
                ATTR_ENTITY_ID: test_entity,
                "option": mode,
            },
            blocking=True,
        )
        mock_set_storage_mode.assert_awaited_once()
        mock_set_storage_mode.assert_called_with(REVERSE_STORAGE_MODE_MAP[mode])
        mock_set_storage_mode.reset_mock()


@pytest.fixture(name="select_envoy")
async def mock_select_envoy_fixture(
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
