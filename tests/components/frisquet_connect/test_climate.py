from datetime import datetime
from decimal import Decimal
import pytest

from frisquet_connect.domains.site.alarm import Alarm
from frisquet_connect.devices.frisquet_connect_coordinator import (
    FrisquetConnectCoordinator,
)
from utils import mock_endpoints, unstub_all

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.climate.const import (
    HVACMode,
    PRESET_NONE,
    PRESET_BOOST,
    PRESET_COMFORT,
    PRESET_SLEEP,
    PRESET_HOME,
    PRESET_AWAY,
    PRESET_ECO,
    PRESET_ACTIVITY,
)

from frisquet_connect.climate import async_setup_entry
from frisquet_connect.const import (
    DOMAIN,
    AlarmType,
    SanitaryWaterMode,
    SanitaryWaterModeLabel,
    SanitaryWaterType,
    ZoneMode,
    ZoneSelector,
)
from frisquet_connect.domains.site.site import Site
from frisquet_connect.domains.site.zone import Zone
from frisquet_connect.entities.climate.default_climate import (
    DefaultClimateEntity,
)
from frisquet_connect.devices.frisquet_connect_device import (
    FrisquetConnectDevice,
)
from tests.conftest import async_core_setup_entry_with_site_id_mutated


async def async_init_climate(
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

    # Assertions
    mock_add_entities.assert_called_once()
    entities = mock_add_entities.call_args[0][0]

    assert len(entities) == 1
    assert isinstance(entities[0], DefaultClimateEntity)

    return entities


@pytest.mark.asyncio
async def test_async_setup_entry_success(
    mock_hass: HomeAssistant,
    mock_entry: ConfigEntry,
    mock_add_entities: AddEntitiesCallback,
):
    entities = await async_init_climate(mock_hass, mock_entry, mock_add_entities)

    entity: DefaultClimateEntity = entities[0]
    if not isinstance(entity, (DefaultClimateEntity)):
        assert False, f"Unknown entity type: {entity.__class__.__name__}"
    entity.update()

    zone: Zone = entity.zone
    assert zone is not None
    assert entity.zone.label_id == "Z1"

    # SITE
    site: Site = entity.coordinator.data
    assert site is not None
    assert (
        str(site.product)
        == "Hydromotrix - Mixte Eau chaude instantanée (Condensation - 32 kW)"
    )
    assert site.serial_number == "A1AB12345"
    assert site.name == "Somewhere"
    assert site.site_id == "12345678901234"
    assert site.last_updated == datetime(2025, 1, 31, 10, 0, 41)
    assert site.external_temperature == Decimal(3.4)

    # SITE.DETAIL
    assert site.detail is not None
    assert site.detail.current_boiler_timestamp == datetime(2025, 1, 31, 10, 3, 40)
    assert site.detail.is_boiler_standby == False
    assert site.detail.is_heat_auto_mode == True

    # SITE.WATER_HEATER
    assert site.water_heater is not None
    assert site.water_heater.sanitary_water_type == SanitaryWaterType.WITHTOU_TANK
    assert site.water_heater.sanitary_water_mode == SanitaryWaterMode.ECO_TIMER

    # SITE.ZONES
    assert site.zones is not None
    assert len(site.zones) == 1
    zone_not_found = site.get_zone_by_label_id("Z2")
    assert zone_not_found is None

    zone: Zone = site.zones[0]
    zone_expected = site.get_zone_by_label_id(zone.label_id)
    assert zone == zone_expected

    assert zone.name == "Zone 1"
    assert zone.label_id == "Z1"
    assert zone.is_boost_available == True

    # SITE.ZONES[0].DETAIL
    assert zone.detail is not None
    assert zone.detail.current_temperature == Decimal(17.0)
    assert zone.detail.target_temperature == Decimal(18.5)
    assert zone.detail.is_exemption_enabled == True
    assert zone.detail.comfort_temperature == Decimal(20.0)
    assert zone.detail.reduced_temperature == Decimal(18.5)
    assert zone.detail.frost_protection_temperature == Decimal(8.0)
    assert zone.detail.is_boosting == False
    assert zone.detail.mode == ZoneMode.REDUCED
    assert zone.detail.selector == ZoneSelector.AUTO

    # SITE.SANITARY_WATER
    assert len(site.available_sanitary_water_modes) == 4
    for mode in site.available_sanitary_water_modes:
        assert mode in SanitaryWaterModeLabel

    # SITE.ALARMS
    assert len(site.alarms) == 1
    alarm: Alarm = site.alarms[0]
    assert alarm.alarme_type == AlarmType.DISCONNECTED
    assert alarm.description == "Box Frisquet Connect déconnectée"

    unstub_all()


@pytest.mark.asyncio
async def test_climate_set_preset_mode(
    mock_hass: HomeAssistant,
    mock_entry: ConfigEntry,
    mock_add_entities: AddEntitiesCallback,
):
    entities = await async_init_climate(mock_hass, mock_entry, mock_add_entities)

    entity: DefaultClimateEntity = entities[0]
    entity.update()

    await entity.async_set_preset_mode(PRESET_NONE)
    await entity.async_set_preset_mode(PRESET_BOOST)
    await entity.async_set_preset_mode(PRESET_HOME)
    await entity.async_set_preset_mode(PRESET_AWAY)
    await entity.async_set_preset_mode(PRESET_COMFORT)
    await entity.async_set_preset_mode(PRESET_SLEEP)
    await entity.async_set_preset_mode(PRESET_ECO)

    unstub_all()


@pytest.mark.asyncio
async def test_climate_set_invalid_preset_mode(
    mock_hass: HomeAssistant,
    mock_entry: ConfigEntry,
    mock_add_entities: AddEntitiesCallback,
):
    entities = await async_init_climate(mock_hass, mock_entry, mock_add_entities)

    entity: DefaultClimateEntity = entities[0]
    with pytest.raises(ValueError):
        await entity.async_set_preset_mode(PRESET_ACTIVITY)

    unstub_all()


@pytest.mark.asyncio
async def test_climate_set_hvac_mode(
    mock_hass: HomeAssistant,
    mock_entry: ConfigEntry,
    mock_add_entities: AddEntitiesCallback,
):
    entities = await async_init_climate(mock_hass, mock_entry, mock_add_entities)

    entity: DefaultClimateEntity = entities[0]
    entity.hass = mock_hass
    entity.update()

    await entity.async_set_hvac_mode(HVACMode.AUTO)
    await entity.async_set_hvac_mode(HVACMode.HEAT)
    await entity.async_set_hvac_mode(HVACMode.OFF)

    unstub_all()


@pytest.mark.asyncio
async def test_climate_set_invalid_hvac_mode(
    mock_hass: HomeAssistant,
    mock_entry: ConfigEntry,
    mock_add_entities: AddEntitiesCallback,
):
    entities = await async_init_climate(mock_hass, mock_entry, mock_add_entities)

    entity: DefaultClimateEntity = entities[0]
    with pytest.raises(ValueError):
        await entity.async_set_hvac_mode(HVACMode.COOL)

    unstub_all()


@pytest.mark.asyncio
async def test_climate_set_temperature(
    mock_hass: HomeAssistant,
    mock_entry: ConfigEntry,
    mock_add_entities: AddEntitiesCallback,
):
    entities = await async_init_climate(mock_hass, mock_entry, mock_add_entities)

    entity: DefaultClimateEntity = entities[0]
    await entity.async_set_temperature(temperature=18.0)

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


@pytest.mark.asyncio
async def test_async_setup_entry_site_id_not_found(
    mock_hass: HomeAssistant,
    mock_entry: ConfigEntry,
    mock_add_entities: AddEntitiesCallback,
):
    await async_core_setup_entry_with_site_id_mutated(
        async_setup_entry, mock_add_entities, mock_hass, mock_entry, "not_found"
    )

    unstub_all()
