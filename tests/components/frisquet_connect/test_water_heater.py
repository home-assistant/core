import pytest

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from homeassistant.helpers.entity_platform import AddEntitiesCallback
from frisquet_connect.devices.frisquet_connect_coordinator import (
    FrisquetConnectCoordinator,
)
from frisquet_connect.entities.water_heater.default_water_heater import (
    DefaultWaterHeaterEntity,
)
from frisquet_connect.water_heater import async_setup_entry
from frisquet_connect.const import (
    DOMAIN,
)
from frisquet_connect.devices.frisquet_connect_device import (
    FrisquetConnectDevice,
)
from tests.conftest import async_core_setup_entry_with_site_id_mutated
from utils import mock_endpoints, unstub_all


@pytest.mark.asyncio
async def test_async_setup_entry_success(
    mock_hass: HomeAssistant,
    mock_entry: ConfigEntry,
    mock_add_entities: AddEntitiesCallback,
):
    # Initialize the mocks
    mock_endpoints()

    # Test the feature
    service = FrisquetConnectDevice(
        mock_entry.data.get("email"), mock_entry.data.get("password")
    )
    coordinator = FrisquetConnectCoordinator(
        mock_hass, service, mock_entry.data.get("site_id")
    )
    await coordinator._async_refresh()
    mock_hass.data[DOMAIN] = {mock_entry.unique_id: coordinator}

    await async_setup_entry(mock_hass, mock_entry, mock_add_entities)

    mock_add_entities.assert_called_once()
    entities = mock_add_entities.call_args[0][0]
    assert len(entities) == 1

    entity: DefaultWaterHeaterEntity = entities[0]
    if not isinstance(entity, (DefaultWaterHeaterEntity)):
        assert False, f"Unknown entity type: {entity.__class__.__name__}"
    entity.update()

    assert entity.current_operation == "Eco Timer"

    unstub_all()


@pytest.mark.asyncio
async def test_async_setup_entry_no_site_id(
    mock_hass: HomeAssistant,
    mock_entry: ConfigEntry,
    mock_add_entities: AddEntitiesCallback,
):
    await async_core_setup_entry_with_site_id_mutated(
        async_setup_entry, mock_add_entities, mock_hass, mock_entry
    )

    unstub_all()
