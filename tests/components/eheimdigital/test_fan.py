"""Tests for the fan module."""

from unittest.mock import AsyncMock, MagicMock, patch

from eheimdigital.types import EheimDeviceType, EheimDigitalClientError, FilterMode
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.eheimdigital.const import (
    FILTER_BIO_MODE,
    FILTER_PULSE_MODE,
)
from homeassistant.components.fan import (
    ATTR_PERCENTAGE,
    ATTR_PRESET_MODE,
    DOMAIN as FAN_DOMAIN,
    SERVICE_SET_PERCENTAGE,
    SERVICE_SET_PRESET_MODE,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .conftest import init_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("classic_vario_mock")
async def test_setup_classic_vario(
    hass: HomeAssistant,
    eheimdigital_hub_mock: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test fan platform setup for filter."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.eheimdigital.PLATFORMS", [Platform.FAN]),
        patch(
            "homeassistant.components.eheimdigital.coordinator.asyncio.Event",
            new=AsyncMock,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)

    await eheimdigital_hub_mock.call_args.kwargs["device_found_callback"](
        "00:00:00:00:00:03", EheimDeviceType.VERSION_EHEIM_CLASSIC_VARIO
    )
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_dynamic_new_devices(
    hass: HomeAssistant,
    eheimdigital_hub_mock: MagicMock,
    classic_vario_mock: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test light platform setup with at first no devices and dynamically adding a device."""
    mock_config_entry.add_to_hass(hass)

    eheimdigital_hub_mock.return_value.devices = {}

    with (
        patch("homeassistant.components.eheimdigital.PLATFORMS", [Platform.FAN]),
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

    eheimdigital_hub_mock.return_value.devices = {
        "00:00:00:00:00:03": classic_vario_mock
    }

    await eheimdigital_hub_mock.call_args.kwargs["device_found_callback"](
        "00:00:00:00:00:03", EheimDeviceType.VERSION_EHEIM_CLASSIC_VARIO
    )
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("preset_mode", "filter_mode"),
    [
        (FILTER_BIO_MODE, FilterMode.BIO),
        (FILTER_PULSE_MODE, FilterMode.PULSE),
    ],
)
async def test_set_preset_mode(
    hass: HomeAssistant,
    eheimdigital_hub_mock: MagicMock,
    classic_vario_mock: MagicMock,
    mock_config_entry: MockConfigEntry,
    preset_mode: str | None,
    filter_mode: FilterMode,
) -> None:
    """Test setting a preset mode."""
    await init_integration(hass, mock_config_entry)

    await eheimdigital_hub_mock.call_args.kwargs["device_found_callback"](
        "00:00:00:00:00:03", EheimDeviceType.VERSION_EHEIM_CLASSIC_VARIO
    )
    await hass.async_block_till_done()

    classic_vario_mock.set_filter_mode.side_effect = EheimDigitalClientError

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {ATTR_ENTITY_ID: "fan.mock_classicvario", ATTR_PRESET_MODE: preset_mode},
            blocking=True,
        )

    classic_vario_mock.set_filter_mode.side_effect = None

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: "fan.mock_classicvario", ATTR_PRESET_MODE: preset_mode},
        blocking=True,
    )

    classic_vario_mock.set_filter_mode.assert_awaited_with(filter_mode)


async def test_set_percentage(
    hass: HomeAssistant,
    eheimdigital_hub_mock: MagicMock,
    classic_vario_mock: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting a percentage."""
    await init_integration(hass, mock_config_entry)

    await eheimdigital_hub_mock.call_args.kwargs["device_found_callback"](
        "00:00:00:00:00:03", EheimDeviceType.VERSION_EHEIM_CLASSIC_VARIO
    )
    await hass.async_block_till_done()

    classic_vario_mock.set_manual_speed.side_effect = EheimDigitalClientError

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_SET_PERCENTAGE,
            {ATTR_ENTITY_ID: "fan.mock_classicvario", ATTR_PERCENTAGE: 50},
            blocking=True,
        )

    classic_vario_mock.set_manual_speed.side_effect = None
    classic_vario_mock.filter_mode = FilterMode.BIO

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {ATTR_ENTITY_ID: "fan.mock_classicvario", ATTR_PERCENTAGE: 50},
        blocking=True,
    )

    classic_vario_mock.set_filter_mode.assert_awaited_with(FilterMode.MANUAL)
    classic_vario_mock.set_manual_speed.assert_awaited_with(50)


async def test_turn_on(
    hass: HomeAssistant,
    eheimdigital_hub_mock: MagicMock,
    classic_vario_mock: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turning on."""
    await init_integration(hass, mock_config_entry)

    await eheimdigital_hub_mock.call_args.kwargs["device_found_callback"](
        "00:00:00:00:00:03", EheimDeviceType.VERSION_EHEIM_CLASSIC_VARIO
    )
    await hass.async_block_till_done()

    classic_vario_mock.set_filter_mode.side_effect = EheimDigitalClientError

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "fan.mock_classicvario", ATTR_PERCENTAGE: 50},
            blocking=True,
        )

    classic_vario_mock.set_filter_mode.side_effect = None

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "fan.mock_classicvario", ATTR_PRESET_MODE: FILTER_BIO_MODE},
        blocking=True,
    )

    classic_vario_mock.set_active.assert_awaited_with(active=True)
    classic_vario_mock.set_filter_mode.assert_awaited_with(FilterMode.BIO)

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "fan.mock_classicvario", ATTR_PERCENTAGE: 50},
        blocking=True,
    )

    classic_vario_mock.set_active.assert_awaited_with(active=True)
    classic_vario_mock.set_filter_mode.assert_awaited_with(FilterMode.MANUAL)
    classic_vario_mock.set_manual_speed.assert_awaited_with(50)


async def test_turn_off(
    hass: HomeAssistant,
    eheimdigital_hub_mock: MagicMock,
    classic_vario_mock: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turning off."""
    await init_integration(hass, mock_config_entry)

    await eheimdigital_hub_mock.call_args.kwargs["device_found_callback"](
        "00:00:00:00:00:03", EheimDeviceType.VERSION_EHEIM_CLASSIC_VARIO
    )
    await hass.async_block_till_done()

    classic_vario_mock.set_active.side_effect = EheimDigitalClientError

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "fan.mock_classicvario"},
            blocking=True,
        )

    classic_vario_mock.set_active.side_effect = None

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "fan.mock_classicvario"},
        blocking=True,
    )

    classic_vario_mock.set_active.assert_awaited_with(active=False)


async def test_state_update(
    hass: HomeAssistant,
    eheimdigital_hub_mock: MagicMock,
    classic_vario_mock: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the fan state update."""
    classic_vario_mock.filter_mode = FilterMode.BIO

    await init_integration(hass, mock_config_entry)

    await eheimdigital_hub_mock.call_args.kwargs["device_found_callback"](
        "00:00:00:00:00:03", EheimDeviceType.VERSION_EHEIM_CLASSIC_VARIO
    )
    await hass.async_block_till_done()

    assert (state := hass.states.get("fan.mock_classicvario"))

    assert state.attributes["preset_mode"] == FILTER_BIO_MODE

    classic_vario_mock.filter_mode = FilterMode.PULSE

    await eheimdigital_hub_mock.call_args.kwargs["receive_callback"]()

    assert (state := hass.states.get("fan.mock_classicvario"))
    assert state.attributes["preset_mode"] == FILTER_PULSE_MODE
