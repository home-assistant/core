"""Tests for the Overkiz fan platform."""

from collections.abc import Generator
from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.fan import (
    ATTR_PERCENTAGE,
    DOMAIN as FAN_DOMAIN,
    SERVICE_SET_PERCENTAGE,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import FixtureDevice, MockOverkizClient, SetupOverkizIntegration
from .helpers import assert_command_call

from tests.common import snapshot_platform

NEXITY = "setup/cloud_nexity_rail_din_europe.json"

AIR_INLET = FixtureDevice(
    NEXITY,
    "io://1234-5678-1698/10001",
    "fan.maple_residence_living_room_air_inlet",
)
AIR_OUTLET = FixtureDevice(
    NEXITY,
    "io://1234-5678-1698/10002",
    "fan.maple_residence_living_room_air_outlet",
)
AIR_TRANSFER = FixtureDevice(
    NEXITY,
    "io://1234-5678-1698/10003",
    "fan.maple_residence_living_room_air_transfer",
)


@pytest.fixture(autouse=True)
def fixture_platforms() -> Generator[None]:
    """Limit platforms to fan only."""
    with patch("homeassistant.components.overkiz.PLATFORMS", [Platform.FAN]):
        yield


async def test_fan_entities_snapshot(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the ventilation point fan entities via snapshot."""
    config_entry = await setup_overkiz_integration(fixture=NEXITY)

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.parametrize(
    ("device", "percentage", "command_name", "parameters"),
    [
        (AIR_INLET, 60, "setAirInput", [60]),
        (AIR_OUTLET, 30, "setAirOutput", [30]),
        (AIR_TRANSFER, 90, "setAirTransfer", [90]),
    ],
    ids=["air-inlet", "air-outlet", "air-transfer"],
)
async def test_fan_set_percentage(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    device: FixtureDevice,
    percentage: int,
    command_name: str,
    parameters: list[int],
) -> None:
    """Test setting the air flow percentage sends the per-widget command."""
    await setup_overkiz_integration(fixture=device.fixture)

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {ATTR_ENTITY_ID: device.entity_id, ATTR_PERCENTAGE: percentage},
        blocking=True,
    )

    assert_command_call(
        mock_client,
        device_url=device.device_url,
        command_name=command_name,
        parameters=parameters,
    )


async def test_fan_set_percentage_zero_turns_off(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
) -> None:
    """Test that setting 0% turns the ventilation point off."""
    await setup_overkiz_integration(fixture=AIR_INLET.fixture)

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {ATTR_ENTITY_ID: AIR_INLET.entity_id, ATTR_PERCENTAGE: 0},
        blocking=True,
    )

    assert_command_call(
        mock_client,
        device_url=AIR_INLET.device_url,
        command_name="off",
        parameters=None,
    )


async def test_fan_turn_off(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
) -> None:
    """Test turning the ventilation point off."""
    await setup_overkiz_integration(fixture=AIR_INLET.fixture)

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: AIR_INLET.entity_id},
        blocking=True,
    )

    assert_command_call(
        mock_client,
        device_url=AIR_INLET.device_url,
        command_name="off",
        parameters=None,
    )


async def test_fan_turn_on_without_percentage(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
) -> None:
    """Test turning on without a percentage uses the on command."""
    await setup_overkiz_integration(fixture=AIR_OUTLET.fixture)

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: AIR_OUTLET.entity_id},
        blocking=True,
    )

    assert_command_call(
        mock_client,
        device_url=AIR_OUTLET.device_url,
        command_name="on",
        parameters=None,
    )


async def test_fan_turn_on_with_percentage(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
) -> None:
    """Test turning on with a percentage sends the air flow command."""
    await setup_overkiz_integration(fixture=AIR_TRANSFER.fixture)

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: AIR_TRANSFER.entity_id, ATTR_PERCENTAGE: 50},
        blocking=True,
    )

    assert_command_call(
        mock_client,
        device_url=AIR_TRANSFER.device_url,
        command_name="setAirTransfer",
        parameters=[50],
    )
