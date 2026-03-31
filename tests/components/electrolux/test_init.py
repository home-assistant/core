"""Unit test for Electrolux init flow."""

from unittest.mock import AsyncMock

from electrolux_group_developer_sdk.client.appliances.appliance_data import (
    ApplianceData,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.electrolux import ElectroluxData
from homeassistant.components.electrolux.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import (
    APPLIANCE_FIXTURES,
    get_fixture_name,
    load_appliance,
    load_appliance_details,
    load_appliance_state,
    setup_integration,
)
from .conftest import appliance_data_factory

from tests.common import MockConfigEntry


@pytest.mark.asyncio
async def test_async_setup_entry_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    appliances: AsyncMock,
    mock_token_manager: AsyncMock,
) -> None:
    """Test successful setup of the Electrolux integration."""
    # Add and setup config entry
    await setup_integration(hass, mock_config_entry)

    # Check integration is loaded
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data is not None
    assert isinstance(mock_config_entry.runtime_data, ElectroluxData)

    # Unload the config entry
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


def test_appliance_fixture_data() -> None:
    """Test that all appliance fixtures are configured correctly."""
    appliance_id_set = set()
    for appliance_fixture in APPLIANCE_FIXTURES:
        appliance = load_appliance(appliance_fixture)
        appliance_id = appliance.applianceId
        assert appliance_id not in appliance_id_set, (
            f"Duplicate appliance ID {appliance_id} detected in fixture {appliance_fixture}"
        )

        appliance_state = load_appliance_state(appliance_fixture)
        assert appliance_id == appliance_state.applianceId, (
            f"Appliance ID in state {appliance_state.applianceId} does not appliance ID in appliance object {appliance_id}"
        )

        appliance_id_set.add(appliance_id)


async def test_all_appliances(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    appliances: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test all entities for all appliance fixtures."""
    await setup_integration(hass, mock_config_entry)

    appliance_list: list[ApplianceData] = await appliances.get_appliance_data()
    for appliance in appliance_list:
        appliance_id = appliance.appliance.applianceId

        device = device_registry.async_get_device({(DOMAIN, appliance_id)})

        assert device is not None
        assert device == snapshot(name=get_fixture_name(appliance_id))


async def test_check_for_new_devices(
    hass: HomeAssistant,
    mock_appliance_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that check_for_new_devices adds and removes devices correctly."""
    old_appliance_fixture = "fenix_oven"
    old_appliance_id = "900412569_00:43319382-443E0748CCD4"

    new_appliance_fixture = "pux_oven"
    new_appliance_id = "949288049_00:11112225-443E076A37D6"

    def set_appliance_fixture_mock(appliance_fixture: str):

        appliance = load_appliance(appliance_fixture)
        details = load_appliance_details(appliance_fixture)
        state = load_appliance_state(appliance_fixture)

        appliance_data = appliance_data_factory(
            appliance=appliance,
            details=details,
            state=state,
        )

        mock_appliance_client.get_appliance_data.return_value = [appliance_data]

    set_appliance_fixture_mock(old_appliance_fixture)

    await setup_integration(hass, mock_config_entry)

    appliance_list: list[
        ApplianceData
    ] = await mock_appliance_client.get_appliance_data()
    assert len(appliance_list) == 1
    assert old_appliance_id == appliance_list[0].appliance.applianceId
    assert get_fixture_name(old_appliance_id) == old_appliance_fixture

    assert device_registry.async_get_device({(DOMAIN, old_appliance_id)}) is not None
    assert device_registry.async_get_device({(DOMAIN, new_appliance_id)}) is None

    set_appliance_fixture_mock(new_appliance_fixture)

    args = mock_appliance_client.start_event_stream.call_args.args
    assert args is not None and len(args) > 0, (
        "start_event_stream method called without any callbacks specified"
    )

    callback_list = args[0]
    for callback in callback_list:
        await callback()

    appliance_list: list[
        ApplianceData
    ] = await mock_appliance_client.get_appliance_data()
    assert len(appliance_list) == 1
    assert new_appliance_id == appliance_list[0].appliance.applianceId
    assert get_fixture_name(new_appliance_id) == new_appliance_fixture

    assert device_registry.async_get_device({(DOMAIN, old_appliance_id)}) is None
    assert device_registry.async_get_device({(DOMAIN, new_appliance_id)}) is not None
