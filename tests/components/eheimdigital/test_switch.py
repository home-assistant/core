"""Tests for the switch module."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.eheimdigital.const import DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import init_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_setup(
    hass: HomeAssistant,
    eheimdigital_hub_mock: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test switch platform setup for the filter."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.eheimdigital.PLATFORMS", [Platform.SWITCH]),
        patch(
            "homeassistant.components.eheimdigital.coordinator.asyncio.Event",
            new=AsyncMock,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)

    for device in eheimdigital_hub_mock.return_value.devices:
        device_obj = eheimdigital_hub_mock.return_value.devices[device]
        await eheimdigital_hub_mock.call_args.kwargs["device_found_callback"](
            device, device_obj.device_type
        )
        for packet in device_obj.packet_mapping:
            await eheimdigital_hub_mock.call_args.kwargs["receive_callback"](
                device_obj.mac_address, packet
            )

        await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_migrate_entities(
    hass: HomeAssistant,
    eheimdigital_hub_mock: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the migration of entity ids."""
    mock_config_entry.add_to_hass(hass)

    entity_registry.async_get_or_create(
        Platform.SWITCH,
        DOMAIN,
        "00:00:00:00:00:05_active",
        config_entry=mock_config_entry,
    )

    with (
        patch("homeassistant.components.eheimdigital.PLATFORMS", [Platform.SWITCH]),
        patch(
            "homeassistant.components.eheimdigital.coordinator.asyncio.Event",
            new=AsyncMock,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)

    for device in eheimdigital_hub_mock.return_value.devices:
        device_obj = eheimdigital_hub_mock.return_value.devices[device]
        await eheimdigital_hub_mock.call_args.kwargs["device_found_callback"](
            device, device_obj.device_type
        )
        for packet in device_obj.packet_mapping:
            await eheimdigital_hub_mock.call_args.kwargs["receive_callback"](
                device_obj.mac_address, packet
            )

        await hass.async_block_till_done()

    assert (
        entity_registry.async_get_entity_id(
            Platform.SWITCH, DOMAIN, "00:00:00:00:00:05_active"
        )
        is None
    )
    assert (
        entity_registry.async_get_entity_id(
            Platform.SWITCH, DOMAIN, "00:00:00:00:00:05_is_active"
        )
        is not None
    )


@pytest.mark.parametrize(
    ("service", "active"), [(SERVICE_TURN_OFF, False), (SERVICE_TURN_ON, True)]
)
@pytest.mark.parametrize(
    ("device_name", "entity_id", "property_name"),
    [
        (
            "classic_vario_mock",
            "switch.mock_aquarium_mock_classicvario",
            "filterActive",
        ),
        ("filter_mock", "switch.mock_aquarium_mock_filter", "active"),
        ("reeflex_mock", "switch.mock_aquarium_mock_reeflex", "isActive"),
        ("reeflex_mock", "switch.mock_aquarium_mock_reeflex_pause", "pause"),
        ("reeflex_mock", "switch.mock_aquarium_mock_reeflex_booster", "booster"),
        ("reeflex_mock", "switch.mock_aquarium_mock_reeflex_expert_mode", "expert"),
    ],
)
async def test_turn_on_off(
    hass: HomeAssistant,
    eheimdigital_hub_mock: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_name: str,
    entity_id: str,
    property_name: str,
    service: str,
    active: bool,
    request: pytest.FixtureRequest,
) -> None:
    """Test turning on/off the switch."""
    device: MagicMock = request.getfixturevalue(device_name)
    await init_integration(hass, mock_config_entry)

    await eheimdigital_hub_mock.call_args.kwargs["device_found_callback"](
        device.mac_address, device.device_type
    )
    for packet in device.packet_mapping:
        await eheimdigital_hub_mock.call_args.kwargs["receive_callback"](
            device.mac_address, packet
        )
    await hass.async_block_till_done()

    await hass.services.async_call(
        SWITCH_DOMAIN,
        service,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    calls = [call for call in device.hub.mock_calls if call[0] == "send_packet"]
    assert calls[-1][1][0][property_name] == int(active)


@pytest.mark.usefixtures("classic_vario_mock", "filter_mock")
@pytest.mark.parametrize(
    ("device_name", "entity_list"),
    [
        (
            "classic_vario_mock",
            [
                (
                    "switch.mock_aquarium_mock_classicvario",
                    "classic_vario_data",
                    "filterActive",
                    1,
                    "on",
                ),
                (
                    "switch.mock_aquarium_mock_classicvario",
                    "classic_vario_data",
                    "filterActive",
                    0,
                    "off",
                ),
            ],
        ),
        (
            "filter_mock",
            [
                (
                    "switch.mock_aquarium_mock_filter",
                    "filter_data",
                    "filterActive",
                    1,
                    "on",
                ),
                (
                    "switch.mock_aquarium_mock_filter",
                    "filter_data",
                    "filterActive",
                    0,
                    "off",
                ),
            ],
        ),
        (
            "reeflex_mock",
            [
                (
                    "switch.mock_aquarium_mock_reeflex",
                    "reeflex_data",
                    "isActive",
                    1,
                    "on",
                ),
                (
                    "switch.mock_aquarium_mock_reeflex",
                    "reeflex_data",
                    "isActive",
                    0,
                    "off",
                ),
                (
                    "switch.mock_aquarium_mock_reeflex_pause",
                    "reeflex_data",
                    "pause",
                    1,
                    "on",
                ),
                (
                    "switch.mock_aquarium_mock_reeflex_pause",
                    "reeflex_data",
                    "pause",
                    0,
                    "off",
                ),
                (
                    "switch.mock_aquarium_mock_reeflex_booster",
                    "reeflex_data",
                    "booster",
                    1,
                    "on",
                ),
                (
                    "switch.mock_aquarium_mock_reeflex_booster",
                    "reeflex_data",
                    "booster",
                    0,
                    "off",
                ),
                (
                    "switch.mock_aquarium_mock_reeflex_expert_mode",
                    "reeflex_data",
                    "expert",
                    1,
                    "on",
                ),
                (
                    "switch.mock_aquarium_mock_reeflex_expert_mode",
                    "reeflex_data",
                    "expert",
                    0,
                    "off",
                ),
            ],
        ),
    ],
)
async def test_state_update(
    hass: HomeAssistant,
    eheimdigital_hub_mock: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_name: str,
    entity_list: list[tuple[str, str, str, float, float]],
    request: pytest.FixtureRequest,
) -> None:
    """Test the switch state update."""
    device: MagicMock = request.getfixturevalue(device_name)
    await init_integration(hass, mock_config_entry)

    await eheimdigital_hub_mock.call_args.kwargs["device_found_callback"](
        device.mac_address, device.device_type
    )
    for packet in device.packet_mapping:
        await eheimdigital_hub_mock.call_args.kwargs["receive_callback"](
            device.mac_address, packet
        )

    await hass.async_block_till_done()

    for item in entity_list:
        getattr(device, item[1])[item[2]] = item[3]
        await eheimdigital_hub_mock.call_args.kwargs["receive_callback"](
            device.mac_address, item[1].upper()
        )
        assert (state := hass.states.get(item[0]))
        assert state.state == str(item[4])
