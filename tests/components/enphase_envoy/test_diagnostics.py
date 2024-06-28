"""Test Enphase Envoy diagnostics."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, Mock, patch

from pyenphase import Envoy, EnvoyTokenAuth
from pyenphase.exceptions import EnvoyError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.enphase_envoy.const import (
    DOMAIN,
    OPTION_DIAGNOSTICS_INCLUDE_FIXTURES,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import load_envoy_fixture

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator

# Fields to exclude from snapshot as they change each run
TO_EXCLUDE = {
    "id",
    "device_id",
    "via_device_id",
    "last_updated",
    "last_changed",
    "last_reported",
}

# fixture files to test
ALL_FIXTURES = (
    [
        pytest.param("envoy", id="envoy"),
        pytest.param("envoy_metered_batt_relay", id="envoy_metered_batt_relay"),
        pytest.param("envoy_nobatt_metered_3p", id="envoy_nobatt_metered_3p"),
        pytest.param("envoy_1p_metered", id="envoy_1p_metered"),
        pytest.param("envoy_tot_cons_metered", id="envoy_tot_cons_metered"),
    ],
)


def limit_diagnostic_attrs(prop, path) -> bool:
    """Mark attributes to exclude from diagnostic snapshot."""
    return prop in TO_EXCLUDE


@pytest.fixture(name="setup_enphase_envoy_diag")
async def setup_enphase_envoy_diag_fixture(
    hass: HomeAssistant,
    config: dict[str, str],
    diag_envoy: AsyncMock,
) -> AsyncGenerator[None, None]:
    """Define a fixture to set up Enphase Envoy."""
    with (
        patch(
            "homeassistant.components.enphase_envoy.config_flow.Envoy",
            return_value=diag_envoy,
        ),
        patch(
            "homeassistant.components.enphase_envoy.Envoy",
            return_value=diag_envoy,
        ),
    ):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
        yield


@pytest.mark.parametrize(("diag_envoy"), *ALL_FIXTURES, indirect=["diag_envoy"])
async def test_entry_diagnostics(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    hass_client: ClientSessionGenerator,
    setup_enphase_envoy_diag: AsyncGenerator[None, None],
    snapshot: SnapshotAssertion,
    diag_envoy: AsyncMock,
) -> None:
    """Test config entry diagnostics."""
    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, config_entry
    )

    assert diagnostics

    # do not use snapshot compare on overall diagnostics as snapshot file content order varies
    # test the individual items of the diagnostics report to avoid false snapshot compare assertions
    assert diagnostics["config_entry"] == snapshot(
        name="config_entry", exclude=limit_diagnostic_attrs
    )
    assert diagnostics["envoy_properties"] == snapshot(
        name="envoy_properties", exclude=limit_diagnostic_attrs
    )
    assert diagnostics["raw_data"] == snapshot(
        name="raw_data", exclude=limit_diagnostic_attrs
    )
    assert diagnostics["envoy_model_data"] == snapshot(
        name="envoy_model_data", exclude=limit_diagnostic_attrs
    )

    assert diagnostics["envoy_entities_by_device"]
    for devices in diagnostics["envoy_entities_by_device"]:
        for entity in devices["entities"]:
            assert entity["entity"] == snapshot(
                name=f"{entity["entity"]["entity_id"]}-entry",
                exclude=limit_diagnostic_attrs,
            )
            assert entity["state"] == snapshot(
                name=f"{entity["entity"]["entity_id"]}-state",
                exclude=limit_diagnostic_attrs,
            )


@pytest.fixture(name="config_entry_options")
def config_entry_options_fixture(
    hass: HomeAssistant, config: dict[str, str], serial_number: str
):
    """Define a config entry fixture."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="45a36e55aaddb2007c5f6602e0c38e72",
        title=f"Envoy {serial_number}" if serial_number else "Envoy",
        unique_id=serial_number,
        data=config,
        options={OPTION_DIAGNOSTICS_INCLUDE_FIXTURES: True},
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture(name="setup_enphase_envoy_options")
async def setup_enphase_envoy_options_fixture(
    hass: HomeAssistant,
    config: dict[str, str],
    diag_envoy: AsyncMock,
) -> AsyncGenerator[None, None]:
    """Define a fixture to set up Enphase Envoy."""
    with (
        patch(
            "homeassistant.components.enphase_envoy.config_flow.Envoy",
            return_value=diag_envoy,
        ),
        patch(
            "homeassistant.components.enphase_envoy.Envoy",
            return_value=diag_envoy,
        ),
    ):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
        yield


@pytest.mark.parametrize(("diag_envoy"), *ALL_FIXTURES, indirect=["diag_envoy"])
async def test_entry_diagnostics_with_fixtures(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry_options: ConfigEntry,
    setup_enphase_envoy_options: AsyncGenerator[None, None],
    snapshot: SnapshotAssertion,
    diag_envoy: AsyncMock,
) -> None:
    """Test config entry diagnostics."""
    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, config_entry_options
    )

    assert diagnostics
    assert diagnostics["fixtures"] == snapshot(
        name="fixtures", exclude=limit_diagnostic_attrs
    )


@pytest.fixture(name="setup_enphase_envoy_diag_options_error")
async def setup_enphase_envoy_diag_options_error_fixture(
    hass: HomeAssistant,
    config: dict[str, str],
    mock_envoy_diag_options_error,
) -> AsyncGenerator[None, None]:
    """Define a fixture to set up Enphase Envoy."""
    with (
        patch(
            "homeassistant.components.enphase_envoy.config_flow.Envoy",
            return_value=mock_envoy_diag_options_error,
        ),
        patch(
            "homeassistant.components.enphase_envoy.Envoy",
            return_value=mock_envoy_diag_options_error,
        ),
    ):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
        yield


@pytest.fixture(name="mock_envoy_diag_options_error")
def mock_envoy_options_fixture(
    diag_envoy,
):
    """Mock envoy with error in request."""
    mock_envoy_options = diag_envoy
    mock_envoy_options.request.side_effect = AsyncMock(side_effect=EnvoyError("Test"))
    return mock_envoy_options


@pytest.mark.parametrize(("diag_envoy"), *ALL_FIXTURES, indirect=["diag_envoy"])
async def test_entry_diagnostics_with_fixtures_with_error(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry_options: ConfigEntry,
    setup_enphase_envoy_diag_options_error: AsyncGenerator[None, None],
    snapshot: SnapshotAssertion,
    diag_envoy: AsyncMock,
) -> None:
    """Test config entry diagnostics."""
    assert await get_diagnostics_for_config_entry(
        hass, hass_client, config_entry_options
    ) == snapshot(exclude=limit_diagnostic_attrs)


@pytest.fixture(name="diag_envoy")
async def mock_diag_envoy_fixture(
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

        response = Mock()
        response.status_code = 200
        response.text = "Testing request \nreplies."
        response.headers = {"Hello": "World"}
        mock_envoy.request = AsyncMock(return_value=response)

        return mock_envoy
