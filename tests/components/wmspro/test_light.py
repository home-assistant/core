"""Test the wmspro light support."""

from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from syrupy import SnapshotAssertion

from homeassistant.components.light import ATTR_BRIGHTNESS
from homeassistant.components.wmspro.const import DOMAIN
from homeassistant.components.wmspro.light import SCAN_INTERVAL
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_config_entry

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_light_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hub_ping: AsyncMock,
    mock_hub_configuration_prod: AsyncMock,
    mock_hub_status_prod_dimmer: AsyncMock,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that a light device is created correctly."""
    assert await setup_config_entry(hass, mock_config_entry)
    assert len(mock_hub_ping.mock_calls) == 1
    assert len(mock_hub_configuration_prod.mock_calls) == 1
    assert len(mock_hub_status_prod_dimmer.mock_calls) == 2

    device_entry = device_registry.async_get_device(identifiers={(DOMAIN, "97358")})
    assert device_entry is not None
    assert device_entry == snapshot


async def test_light_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hub_ping: AsyncMock,
    mock_hub_configuration_prod: AsyncMock,
    mock_hub_status_prod_dimmer: AsyncMock,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that a light entity is created and updated correctly."""
    assert await setup_config_entry(hass, mock_config_entry)
    assert len(mock_hub_ping.mock_calls) == 1
    assert len(mock_hub_configuration_prod.mock_calls) == 1
    assert len(mock_hub_status_prod_dimmer.mock_calls) == 2

    entity = hass.states.get("light.licht")
    assert entity is not None
    assert entity == snapshot

    # Move time to next update
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert len(mock_hub_status_prod_dimmer.mock_calls) >= 3


async def test_light_turn_on_and_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hub_ping: AsyncMock,
    mock_hub_configuration_prod: AsyncMock,
    mock_hub_status_prod_dimmer: AsyncMock,
    mock_action_call: AsyncMock,
) -> None:
    """Test that a light entity is turned on and off correctly."""
    assert await setup_config_entry(hass, mock_config_entry)
    assert len(mock_hub_ping.mock_calls) == 1
    assert len(mock_hub_configuration_prod.mock_calls) == 1
    assert len(mock_hub_status_prod_dimmer.mock_calls) >= 1

    entity = hass.states.get("light.licht")
    assert entity is not None
    assert entity.state == STATE_OFF
    assert entity.attributes[ATTR_BRIGHTNESS] is None

    with patch(
        "wmspro.destination.Destination.refresh",
        return_value=True,
    ):
        before = len(mock_hub_status_prod_dimmer.mock_calls)

        await hass.services.async_call(
            Platform.LIGHT,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: entity.entity_id},
            blocking=True,
        )

        entity = hass.states.get("light.licht")
        assert entity is not None
        assert entity.state == STATE_ON
        assert entity.attributes[ATTR_BRIGHTNESS] >= 1
        assert len(mock_hub_status_prod_dimmer.mock_calls) == before

    with patch(
        "wmspro.destination.Destination.refresh",
        return_value=True,
    ):
        before = len(mock_hub_status_prod_dimmer.mock_calls)

        await hass.services.async_call(
            Platform.LIGHT,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: entity.entity_id},
            blocking=True,
        )

        entity = hass.states.get("light.licht")
        assert entity is not None
        assert entity.state == STATE_OFF
        assert entity.attributes[ATTR_BRIGHTNESS] is None
        assert len(mock_hub_status_prod_dimmer.mock_calls) == before


async def test_light_dimm_on_and_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hub_ping: AsyncMock,
    mock_hub_configuration_prod: AsyncMock,
    mock_hub_status_prod_dimmer: AsyncMock,
    mock_action_call: AsyncMock,
) -> None:
    """Test that a light entity is dimmed on and off correctly."""
    assert await setup_config_entry(hass, mock_config_entry)
    assert len(mock_hub_ping.mock_calls) == 1
    assert len(mock_hub_configuration_prod.mock_calls) == 1
    assert len(mock_hub_status_prod_dimmer.mock_calls) >= 1

    entity = hass.states.get("light.licht")
    assert entity is not None
    assert entity.state == STATE_OFF
    assert entity.attributes[ATTR_BRIGHTNESS] is None

    with patch(
        "wmspro.destination.Destination.refresh",
        return_value=True,
    ):
        before = len(mock_hub_status_prod_dimmer.mock_calls)

        await hass.services.async_call(
            Platform.LIGHT,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: entity.entity_id},
            blocking=True,
        )

        entity = hass.states.get("light.licht")
        assert entity is not None
        assert entity.state == STATE_ON
        assert entity.attributes[ATTR_BRIGHTNESS] >= 1
        assert len(mock_hub_status_prod_dimmer.mock_calls) == before

    with patch(
        "wmspro.destination.Destination.refresh",
        return_value=True,
    ):
        before = len(mock_hub_status_prod_dimmer.mock_calls)

        await hass.services.async_call(
            Platform.LIGHT,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: entity.entity_id, ATTR_BRIGHTNESS: 128},
            blocking=True,
        )

        entity = hass.states.get("light.licht")
        assert entity is not None
        assert entity.state == STATE_ON
        assert entity.attributes[ATTR_BRIGHTNESS] == 128
        assert len(mock_hub_status_prod_dimmer.mock_calls) == before

    with patch(
        "wmspro.destination.Destination.refresh",
        return_value=True,
    ):
        before = len(mock_hub_status_prod_dimmer.mock_calls)

        await hass.services.async_call(
            Platform.LIGHT,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: entity.entity_id},
            blocking=True,
        )

        entity = hass.states.get("light.licht")
        assert entity is not None
        assert entity.state == STATE_OFF
        assert entity.attributes[ATTR_BRIGHTNESS] is None
        assert len(mock_hub_status_prod_dimmer.mock_calls) == before
