"""Tests for the climate module."""

from unittest.mock import AsyncMock, MagicMock, patch

from eheimdigital.types import (
    EheimDeviceType,
    EheimDigitalClientError,
    HeaterMode,
    HeaterUnit,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    PRESET_NONE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACAction,
    HVACMode,
)
from homeassistant.components.eheimdigital.const import (
    HEATER_BIO_MODE,
    HEATER_SMART_MODE,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .conftest import init_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("heater_mock")
async def test_setup_heater(
    hass: HomeAssistant,
    eheimdigital_hub_mock: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test climate platform setup for heater."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.eheimdigital.PLATFORMS", [Platform.CLIMATE]),
        patch(
            "homeassistant.components.eheimdigital.coordinator.asyncio.Event",
            new=AsyncMock,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)

    await eheimdigital_hub_mock.call_args.kwargs["device_found_callback"](
        "00:00:00:00:00:02", EheimDeviceType.VERSION_EHEIM_EXT_HEATER
    )
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_dynamic_new_devices(
    hass: HomeAssistant,
    eheimdigital_hub_mock: MagicMock,
    heater_mock: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test light platform setup with at first no devices and dynamically adding a device."""
    mock_config_entry.add_to_hass(hass)

    eheimdigital_hub_mock.return_value.devices = {}

    with (
        patch("homeassistant.components.eheimdigital.PLATFORMS", [Platform.CLIMATE]),
        patch(
            "homeassistant.components.eheimdigital.coordinator.asyncio.Event",
            new=AsyncMock,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert (
        len(
            entity_registry.entities.get_entries_for_config_entry_id(
                mock_config_entry.entry_id
            )
        )
        == 0
    )

    eheimdigital_hub_mock.return_value.devices = {"00:00:00:00:00:02": heater_mock}

    await eheimdigital_hub_mock.call_args.kwargs["device_found_callback"](
        "00:00:00:00:00:02", EheimDeviceType.VERSION_EHEIM_EXT_HEATER
    )
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("preset_mode", "heater_mode"),
    [
        (PRESET_NONE, HeaterMode.MANUAL),
        (HEATER_BIO_MODE, HeaterMode.BIO),
        (HEATER_SMART_MODE, HeaterMode.SMART),
    ],
)
async def test_set_preset_mode(
    hass: HomeAssistant,
    eheimdigital_hub_mock: MagicMock,
    heater_mock: MagicMock,
    mock_config_entry: MockConfigEntry,
    preset_mode: str,
    heater_mode: HeaterMode,
) -> None:
    """Test setting a preset mode."""
    await init_integration(hass, mock_config_entry)

    await eheimdigital_hub_mock.call_args.kwargs["device_found_callback"](
        "00:00:00:00:00:02", EheimDeviceType.VERSION_EHEIM_EXT_HEATER
    )
    await hass.async_block_till_done()

    heater_mock.set_operation_mode.side_effect = EheimDigitalClientError

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {ATTR_ENTITY_ID: "climate.mock_heater", ATTR_PRESET_MODE: preset_mode},
            blocking=True,
        )

    heater_mock.set_operation_mode.side_effect = None

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: "climate.mock_heater", ATTR_PRESET_MODE: preset_mode},
        blocking=True,
    )

    heater_mock.set_operation_mode.assert_awaited_with(heater_mode)


async def test_set_temperature(
    hass: HomeAssistant,
    eheimdigital_hub_mock: MagicMock,
    heater_mock: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting a preset mode."""
    await init_integration(hass, mock_config_entry)

    await eheimdigital_hub_mock.call_args.kwargs["device_found_callback"](
        "00:00:00:00:00:02", EheimDeviceType.VERSION_EHEIM_EXT_HEATER
    )
    await hass.async_block_till_done()

    heater_mock.set_target_temperature.side_effect = EheimDigitalClientError

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: "climate.mock_heater", ATTR_TEMPERATURE: 26.0},
            blocking=True,
        )

    heater_mock.set_target_temperature.side_effect = None

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: "climate.mock_heater", ATTR_TEMPERATURE: 26.0},
        blocking=True,
    )

    heater_mock.set_target_temperature.assert_awaited_with(26.0)


@pytest.mark.parametrize(
    ("hvac_mode", "active"), [(HVACMode.AUTO, True), (HVACMode.OFF, False)]
)
async def test_set_hvac_mode(
    hass: HomeAssistant,
    eheimdigital_hub_mock: MagicMock,
    heater_mock: MagicMock,
    mock_config_entry: MockConfigEntry,
    hvac_mode: HVACMode,
    active: bool,
) -> None:
    """Test setting a preset mode."""
    await init_integration(hass, mock_config_entry)

    await eheimdigital_hub_mock.call_args.kwargs["device_found_callback"](
        "00:00:00:00:00:02", EheimDeviceType.VERSION_EHEIM_EXT_HEATER
    )
    await hass.async_block_till_done()

    heater_mock.set_active.side_effect = EheimDigitalClientError

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: "climate.mock_heater", ATTR_HVAC_MODE: hvac_mode},
            blocking=True,
        )

    heater_mock.set_active.side_effect = None

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: "climate.mock_heater", ATTR_HVAC_MODE: hvac_mode},
        blocking=True,
    )

    heater_mock.set_active.assert_awaited_with(active=active)


async def test_state_update(
    hass: HomeAssistant,
    eheimdigital_hub_mock: MagicMock,
    mock_config_entry: MockConfigEntry,
    heater_mock: MagicMock,
) -> None:
    """Test the climate state update."""
    heater_mock.temperature_unit = HeaterUnit.FAHRENHEIT
    heater_mock.is_heating = False
    heater_mock.operation_mode = HeaterMode.BIO

    await init_integration(hass, mock_config_entry)

    await eheimdigital_hub_mock.call_args.kwargs["device_found_callback"](
        "00:00:00:00:00:02", EheimDeviceType.VERSION_EHEIM_EXT_HEATER
    )
    await hass.async_block_till_done()

    assert (state := hass.states.get("climate.mock_heater"))

    assert state.attributes["hvac_action"] == HVACAction.IDLE
    assert state.attributes["preset_mode"] == HEATER_BIO_MODE

    heater_mock.is_active = False
    heater_mock.operation_mode = HeaterMode.SMART

    await eheimdigital_hub_mock.call_args.kwargs["receive_callback"]()

    assert (state := hass.states.get("climate.mock_heater"))
    assert state.state == HVACMode.OFF
    assert state.attributes["preset_mode"] == HEATER_SMART_MODE
