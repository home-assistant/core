"""Test Enphase Envoy number sensors."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, Mock, patch

from pyenphase import Envoy, EnvoyTokenAuth
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.enphase_envoy import DOMAIN
from homeassistant.components.enphase_envoy.const import Platform
from homeassistant.components.number import SERVICE_SET_VALUE
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from . import load_envoy_fixture

from tests.common import MockConfigEntry

NUMBER_FIXTURES = (
    [
        pytest.param("envoy_metered_batt_relay", 7, id="envoy_metered_batt_relay"),
    ],
)


@pytest.fixture(name="setup_enphase_envoy_number")
async def setup_enphase_envoy_number_fixture(
    hass: HomeAssistant, config: dict[str, str], number_envoy: AsyncMock
) -> AsyncGenerator[None, None]:
    """Define a fixture to set up Enphase Envoy with number platform only."""
    with (
        patch(
            "homeassistant.components.enphase_envoy.config_flow.Envoy",
            return_value=number_envoy,
        ),
        patch(
            "homeassistant.components.enphase_envoy.Envoy",
            return_value=number_envoy,
        ),
        patch(
            "homeassistant.components.enphase_envoy.PLATFORMS",
            [Platform.NUMBER],
        ),
    ):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
        yield


@pytest.mark.parametrize(
    ("number_envoy", "entity_count"), *NUMBER_FIXTURES, indirect=["number_envoy"]
)
async def test_number_operation(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    setup_enphase_envoy_number: None,
    mock_set_reserve_soc: AsyncMock,
    number_envoy: AsyncMock,
    entity_count: int,
) -> None:
    """Test enphase_envoy number entities operation."""
    assert len(hass.states.async_all()) == entity_count

    entity_base = f"{Platform.NUMBER}.enpower_"

    sn = number_envoy.data.enpower.serial_number
    test_entity = f"{entity_base}{sn}_reserve_battery_level"
    assert (entity_state := hass.states.get(test_entity))
    assert number_envoy.data.tariff.storage_settings.reserved_soc == float(
        entity_state.state
    )
    test_value = 2 * float(entity_state.state)
    await hass.services.async_call(
        Platform.NUMBER,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: test_entity,
            "value": test_value,
        },
        blocking=True,
    )

    mock_set_reserve_soc.assert_awaited_once()
    mock_set_reserve_soc.assert_called_with(test_value)
    mock_set_reserve_soc.reset_mock()


@pytest.fixture(name="number_envoy")
async def mock_number_envoy_fixture(
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
