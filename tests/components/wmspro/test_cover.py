"""Test the wmspro cover support."""

from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_CURRENT_TILT_POSITION,
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    DOMAIN as COVER_DOMAIN,
)
from homeassistant.components.wmspro.const import DOMAIN
from homeassistant.components.wmspro.cover import SCAN_INTERVAL
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_CLOSE_COVER,
    SERVICE_CLOSE_COVER_TILT,
    SERVICE_OPEN_COVER,
    SERVICE_OPEN_COVER_TILT,
    SERVICE_SET_COVER_POSITION,
    SERVICE_SET_COVER_TILT_POSITION,
    SERVICE_STOP_COVER,
    STATE_CLOSED,
    STATE_OPEN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_config_entry

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.parametrize(
    ("mock_hub_configuration", "mock_hub_status"),
    [("config_prod_awning_dimmer.json", "status_prod_awning.json")],
    indirect=True,
)
async def test_cover_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hub_ping: AsyncMock,
    mock_hub_configuration: AsyncMock,
    mock_hub_status: AsyncMock,
    freezer: FrozenDateTimeFactory,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that a cover device is created correctly."""
    assert await setup_config_entry(hass, mock_config_entry)
    assert len(mock_hub_ping.mock_calls) == 1
    assert len(mock_hub_configuration.mock_calls) == 1
    assert len(mock_hub_status.mock_calls) == len(mock_hub_configuration.destinations)

    device_entry = device_registry.async_get_device(identifiers={(DOMAIN, "58717")})
    assert device_entry is not None
    assert device_entry == snapshot


@pytest.mark.parametrize(
    ("mock_hub_configuration", "mock_hub_status"),
    [("config_prod_awning_dimmer.json", "status_prod_awning.json")],
    indirect=True,
)
async def test_cover_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hub_ping: AsyncMock,
    mock_hub_configuration: AsyncMock,
    mock_hub_status: AsyncMock,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that a cover entity is created and updated correctly."""
    assert await setup_config_entry(hass, mock_config_entry)
    assert len(mock_hub_ping.mock_calls) == 1
    assert len(mock_hub_configuration.mock_calls) == 1
    assert len(mock_hub_status.mock_calls) == len(mock_hub_configuration.destinations)

    entity = hass.states.get("cover.terrasse_markise")
    assert entity is not None
    assert entity == snapshot

    before_status = len(mock_hub_status.mock_calls)

    # Move time to next update
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert len(mock_hub_status.mock_calls) == before_status + 1


@pytest.mark.parametrize(
    (
        "mock_hub_configuration",
        "mock_hub_status",
        "entity_id",
        "num_action",
        "num_action_list",
    ),
    [
        (
            "config_prod_awning_dimmer.json",
            "status_prod_awning.json",
            "cover.terrasse_markise",
            1,
            0,
        ),
        (
            "config_prod_awning_valance.json",
            "status_prod_valance.json",
            "cover.raum_0_markise_2",
            1,
            0,
        ),
        (
            "config_prod_roller_shutter.json",
            "status_prod_roller_shutter.json",
            "cover.wohnbereich_wohnebene_alle",
            1,
            0,
        ),
        (
            "config_prod_slat_drive.json",
            "status_prod_slat_drive.json",
            "cover.terrasse_lamellen",
            1,
            0,
        ),
        (
            "config_prod_slat_rotate.json",
            "status_prod_slat_rotate.json",
            "cover.zonwering_begane_grond_keuken_alle",
            2,
            1,
        ),
    ],
    indirect=["mock_hub_configuration", "mock_hub_status"],
)
async def test_cover_open_and_close(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hub_ping: AsyncMock,
    mock_hub_configuration: AsyncMock,
    mock_hub_status: AsyncMock,
    mock_action_call: AsyncMock,
    mock_action_list_call: AsyncMock,
    entity_id: str,
    num_action: int,
    num_action_list: int,
) -> None:
    """Test that a cover entity is opened and closed correctly."""
    assert await setup_config_entry(hass, mock_config_entry)
    assert len(mock_hub_ping.mock_calls) == 1
    assert len(mock_hub_configuration.mock_calls) == 1
    assert len(mock_hub_status.mock_calls) == len(mock_hub_configuration.destinations)

    entity = hass.states.get(entity_id)
    assert entity is not None
    assert entity.state == STATE_CLOSED
    assert entity.attributes[ATTR_CURRENT_POSITION] == 0

    with patch(
        "wmspro.destination.Destination.refresh",
        return_value=True,
    ):
        before_status = len(mock_hub_status.mock_calls)
        before_action = len(mock_action_call.mock_calls)
        before_action_list = len(mock_action_list_call.mock_calls)

        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_OPEN_COVER,
            {ATTR_ENTITY_ID: entity.entity_id},
            blocking=True,
        )

        entity = hass.states.get(entity_id)
        assert entity is not None
        assert entity.state == STATE_OPEN
        assert entity.attributes[ATTR_CURRENT_POSITION] == 100
        assert len(mock_hub_status.mock_calls) == before_status
        assert len(mock_action_call.mock_calls) == before_action + num_action
        assert (
            len(mock_action_list_call.mock_calls)
            == before_action_list + num_action_list
        )

    with patch(
        "wmspro.destination.Destination.refresh",
        return_value=True,
    ):
        before_status = len(mock_hub_status.mock_calls)
        before_action = len(mock_action_call.mock_calls)
        before_action_list = len(mock_action_list_call.mock_calls)

        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_CLOSE_COVER,
            {ATTR_ENTITY_ID: entity.entity_id},
            blocking=True,
        )

        entity = hass.states.get(entity_id)
        assert entity is not None
        assert entity.state == STATE_CLOSED
        assert entity.attributes[ATTR_CURRENT_POSITION] == 0
        assert len(mock_hub_status.mock_calls) == before_status
        assert len(mock_action_call.mock_calls) == before_action + num_action
        assert (
            len(mock_action_list_call.mock_calls)
            == before_action_list + num_action_list
        )


@pytest.mark.parametrize(
    ("mock_hub_configuration", "mock_hub_status", "entity_id"),
    [
        (
            "config_prod_awning_dimmer.json",
            "status_prod_awning.json",
            "cover.terrasse_markise",
        ),
        (
            "config_prod_awning_valance.json",
            "status_prod_valance.json",
            "cover.raum_0_markise_2",
        ),
        (
            "config_prod_roller_shutter.json",
            "status_prod_roller_shutter.json",
            "cover.wohnbereich_wohnebene_alle",
        ),
        (
            "config_prod_slat_drive.json",
            "status_prod_slat_drive.json",
            "cover.terrasse_lamellen",
        ),
        (
            "config_prod_slat_rotate.json",
            "status_prod_slat_rotate.json",
            "cover.zonwering_begane_grond_keuken_alle",
        ),
    ],
    indirect=["mock_hub_configuration", "mock_hub_status"],
)
async def test_cover_open_to_pos(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hub_ping: AsyncMock,
    mock_hub_configuration: AsyncMock,
    mock_hub_status: AsyncMock,
    mock_action_call: AsyncMock,
    entity_id: str,
) -> None:
    """Test that a cover entity is opened to correct position."""
    assert await setup_config_entry(hass, mock_config_entry)
    assert len(mock_hub_ping.mock_calls) == 1
    assert len(mock_hub_configuration.mock_calls) == 1
    assert len(mock_hub_status.mock_calls) == len(mock_hub_configuration.destinations)

    entity = hass.states.get(entity_id)
    assert entity is not None
    assert entity.state == STATE_CLOSED
    assert entity.attributes[ATTR_CURRENT_POSITION] == 0

    with patch(
        "wmspro.destination.Destination.refresh",
        return_value=True,
    ):
        before_status = len(mock_hub_status.mock_calls)
        before_action = len(mock_action_call.mock_calls)

        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_SET_COVER_POSITION,
            {ATTR_ENTITY_ID: entity.entity_id, ATTR_POSITION: 50},
            blocking=True,
        )

        entity = hass.states.get(entity_id)
        assert entity is not None
        assert entity.state == STATE_OPEN
        assert entity.attributes[ATTR_CURRENT_POSITION] == 50
        assert len(mock_hub_status.mock_calls) == before_status
        assert len(mock_action_call.mock_calls) == before_action + 1


@pytest.mark.parametrize(
    ("mock_hub_configuration", "mock_hub_status", "entity_id"),
    [
        (
            "config_prod_awning_dimmer.json",
            "status_prod_awning.json",
            "cover.terrasse_markise",
        ),
        (
            "config_prod_awning_valance.json",
            "status_prod_valance.json",
            "cover.raum_0_markise_2",
        ),
        (
            "config_prod_roller_shutter.json",
            "status_prod_roller_shutter.json",
            "cover.wohnbereich_wohnebene_alle",
        ),
        (
            "config_prod_slat_drive.json",
            "status_prod_slat_drive.json",
            "cover.terrasse_lamellen",
        ),
        (
            "config_prod_slat_rotate.json",
            "status_prod_slat_rotate.json",
            "cover.zonwering_begane_grond_keuken_alle",
        ),
    ],
    indirect=["mock_hub_configuration", "mock_hub_status"],
)
async def test_cover_open_and_stop(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hub_ping: AsyncMock,
    mock_hub_configuration: AsyncMock,
    mock_hub_status: AsyncMock,
    mock_action_call: AsyncMock,
    entity_id: str,
) -> None:
    """Test that a cover entity is opened and stopped correctly."""
    assert await setup_config_entry(hass, mock_config_entry)
    assert len(mock_hub_ping.mock_calls) == 1
    assert len(mock_hub_configuration.mock_calls) == 1
    assert len(mock_hub_status.mock_calls) == len(mock_hub_configuration.destinations)

    entity = hass.states.get(entity_id)
    assert entity is not None
    assert entity.state == STATE_CLOSED
    assert entity.attributes[ATTR_CURRENT_POSITION] == 0

    with patch(
        "wmspro.destination.Destination.refresh",
        return_value=True,
    ):
        before_status = len(mock_hub_status.mock_calls)
        before_action = len(mock_action_call.mock_calls)

        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_SET_COVER_POSITION,
            {ATTR_ENTITY_ID: entity.entity_id, ATTR_POSITION: 80},
            blocking=True,
        )

        entity = hass.states.get(entity_id)
        assert entity is not None
        assert entity.state == STATE_OPEN
        assert entity.attributes[ATTR_CURRENT_POSITION] == 80
        assert len(mock_hub_status.mock_calls) == before_status
        assert len(mock_action_call.mock_calls) == before_action + 1

    with patch(
        "wmspro.destination.Destination.refresh",
        return_value=True,
    ):
        before_status = len(mock_hub_status.mock_calls)
        before_action = len(mock_action_call.mock_calls)

        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_STOP_COVER,
            {ATTR_ENTITY_ID: entity.entity_id},
            blocking=True,
        )

        entity = hass.states.get(entity_id)
        assert entity is not None
        assert entity.state == STATE_OPEN
        assert entity.attributes[ATTR_CURRENT_POSITION] == 80
        assert len(mock_hub_status.mock_calls) == before_status
        assert len(mock_action_call.mock_calls) == before_action + 1


@pytest.mark.parametrize(
    ("mock_hub_configuration", "mock_hub_status", "entity_id"),
    [
        (
            "config_prod_slat_rotate.json",
            "status_prod_slat_rotate.json",
            "cover.zonwering_begane_grond_keuken_alle",
        ),
    ],
    indirect=["mock_hub_configuration", "mock_hub_status"],
)
async def test_cover_tilt_open_and_close(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hub_ping: AsyncMock,
    mock_hub_configuration: AsyncMock,
    mock_hub_status: AsyncMock,
    mock_action_call: AsyncMock,
    entity_id: str,
) -> None:
    """Test that a cover entity is tilted open and closed correctly."""
    assert await setup_config_entry(hass, mock_config_entry)
    assert len(mock_hub_ping.mock_calls) == 1
    assert len(mock_hub_configuration.mock_calls) == 1
    assert len(mock_hub_status.mock_calls) == len(mock_hub_configuration.destinations)

    await hass.async_block_till_done(wait_background_tasks=True)

    entity = hass.states.get(entity_id)
    assert entity is not None
    assert entity.attributes[ATTR_CURRENT_TILT_POSITION] == 50

    with patch(
        "wmspro.destination.Destination.refresh",
        return_value=True,
    ):
        before_status = len(mock_hub_status.mock_calls)
        before_action = len(mock_action_call.mock_calls)

        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_CLOSE_COVER_TILT,
            {ATTR_ENTITY_ID: entity.entity_id},
            blocking=True,
        )

        entity = hass.states.get(entity_id)
        assert entity is not None
        assert entity.attributes[ATTR_CURRENT_TILT_POSITION] == 0
        assert len(mock_hub_status.mock_calls) == before_status
        assert len(mock_action_call.mock_calls) == before_action + 1

    with patch(
        "wmspro.destination.Destination.refresh",
        return_value=True,
    ):
        before_status = len(mock_hub_status.mock_calls)
        before_action = len(mock_action_call.mock_calls)

        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_OPEN_COVER_TILT,
            {ATTR_ENTITY_ID: entity.entity_id},
            blocking=True,
        )

        entity = hass.states.get(entity_id)
        assert entity is not None
        assert entity.attributes[ATTR_CURRENT_TILT_POSITION] == 50
        assert len(mock_hub_status.mock_calls) == before_status
        assert len(mock_action_call.mock_calls) == before_action + 1


@pytest.mark.parametrize(
    ("mock_hub_configuration", "mock_hub_status", "entity_id"),
    [
        (
            "config_prod_slat_rotate.json",
            "status_prod_slat_rotate.json",
            "cover.zonwering_begane_grond_keuken_alle",
        ),
    ],
    indirect=["mock_hub_configuration", "mock_hub_status"],
)
async def test_cover_tilt_to_pos(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hub_ping: AsyncMock,
    mock_hub_configuration: AsyncMock,
    mock_hub_status: AsyncMock,
    mock_action_call: AsyncMock,
    entity_id: str,
) -> None:
    """Test that a cover entity is tilted to correct position."""
    assert await setup_config_entry(hass, mock_config_entry)
    assert len(mock_hub_ping.mock_calls) == 1
    assert len(mock_hub_configuration.mock_calls) == 1
    assert len(mock_hub_status.mock_calls) == len(mock_hub_configuration.destinations)

    await hass.async_block_till_done(wait_background_tasks=True)

    entity = hass.states.get(entity_id)
    assert entity is not None
    assert entity.attributes[ATTR_CURRENT_TILT_POSITION] == 50

    with patch(
        "wmspro.destination.Destination.refresh",
        return_value=True,
    ):
        before_status = len(mock_hub_status.mock_calls)
        before_action = len(mock_action_call.mock_calls)

        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_SET_COVER_TILT_POSITION,
            {ATTR_ENTITY_ID: entity.entity_id, ATTR_TILT_POSITION: 100},
            blocking=True,
        )

        entity = hass.states.get(entity_id)
        assert entity is not None
        assert entity.attributes[ATTR_CURRENT_TILT_POSITION] == 100
        assert len(mock_hub_status.mock_calls) == before_status
        assert len(mock_action_call.mock_calls) == before_action + 1


@pytest.mark.parametrize(
    (
        "mock_hub_configuration",
        "mock_hub_status",
        "entity_id",
        "num_action",
        "num_action_list",
    ),
    [
        (
            "config_prod_slat_rotate.json",
            "status_prod_slat_rotate.json",
            "cover.zonwering_begane_grond_keuken_alle",
            2,
            1,
        ),
    ],
    indirect=["mock_hub_configuration", "mock_hub_status"],
)
async def test_cover_tilt_with_open_and_close_pos(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hub_ping: AsyncMock,
    mock_hub_configuration: AsyncMock,
    mock_hub_status: AsyncMock,
    mock_action_call: AsyncMock,
    mock_action_list_call: AsyncMock,
    entity_id: str,
    num_action: int,
    num_action_list: int,
) -> None:
    """Test that a cover entity is tilted to correct position."""
    assert await setup_config_entry(hass, mock_config_entry)
    assert len(mock_hub_ping.mock_calls) == 1
    assert len(mock_hub_configuration.mock_calls) == 1
    assert len(mock_hub_status.mock_calls) == len(mock_hub_configuration.destinations)

    await hass.async_block_till_done(wait_background_tasks=True)

    entity = hass.states.get(entity_id)
    assert entity is not None
    assert entity.state == STATE_CLOSED
    assert entity.attributes[ATTR_CURRENT_POSITION] == 0
    assert entity.attributes[ATTR_CURRENT_TILT_POSITION] == 50

    with patch(
        "wmspro.destination.Destination.refresh",
        return_value=True,
    ):
        before_status = len(mock_hub_status.mock_calls)
        before_action = len(mock_action_call.mock_calls)
        before_action_list = len(mock_action_list_call.mock_calls)

        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_SET_COVER_POSITION,
            {ATTR_ENTITY_ID: entity.entity_id, ATTR_POSITION: 100},
            blocking=True,
        )

        entity = hass.states.get(entity_id)
        assert entity is not None
        assert entity.state == STATE_OPEN
        assert entity.attributes[ATTR_CURRENT_POSITION] == 100
        assert entity.attributes[ATTR_CURRENT_TILT_POSITION] == 100
        assert len(mock_hub_status.mock_calls) == before_status
        assert len(mock_action_call.mock_calls) == before_action + num_action
        assert (
            len(mock_action_list_call.mock_calls)
            == before_action_list + num_action_list
        )

    with patch(
        "wmspro.destination.Destination.refresh",
        return_value=True,
    ):
        before_status = len(mock_hub_status.mock_calls)
        before_action = len(mock_action_call.mock_calls)
        before_action_list = len(mock_action_list_call.mock_calls)

        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_SET_COVER_POSITION,
            {ATTR_ENTITY_ID: entity.entity_id, ATTR_POSITION: 0},
            blocking=True,
        )

        entity = hass.states.get(entity_id)
        assert entity is not None
        assert entity.state == STATE_CLOSED
        assert entity.attributes[ATTR_CURRENT_POSITION] == 0
        assert entity.attributes[ATTR_CURRENT_TILT_POSITION] == 0
        assert len(mock_hub_status.mock_calls) == before_status
        assert len(mock_action_call.mock_calls) == before_action + num_action
        assert (
            len(mock_action_list_call.mock_calls)
            == before_action_list + num_action_list
        )
