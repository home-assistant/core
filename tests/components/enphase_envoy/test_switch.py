"""Test Enphase Envoy switch."""

from unittest.mock import AsyncMock

from pyenphase.models.dry_contacts import DryContactStatus
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.enphase_envoy.const import Platform
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry
from tests.components.enphase_envoy import setup_with_selected_platforms
from tests.components.enphase_envoy.conftest import ALL_FIXTURES, SWITCH_FIXTURES


@pytest.mark.parametrize(
    ("mock_envoy", "entity_count"), *SWITCH_FIXTURES, indirect=["mock_envoy"]
)
async def test_switch(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    mock_envoy: AsyncMock,
    entity_registry: AsyncMock,
    entity_count: int,
) -> None:
    """Test enphase_envoy switch entities."""
    await setup_with_selected_platforms(hass, config_entry, [Platform.SWITCH])

    # number entities states should be created from test data
    assert len(hass.states.async_all()) == entity_count

    entity_entries = er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )

    assert len(entity_entries) == entity_count
    # compare registered entities against snapshot of prior run
    for entity_entry in entity_entries:
        assert entity_entry == snapshot(name=f"{entity_entry.entity_id}-entry")
        assert hass.states.get(entity_entry.entity_id) == snapshot(
            name=f"{entity_entry.entity_id}-state"
        )


@pytest.mark.parametrize(("mock_envoy"), *ALL_FIXTURES, indirect=["mock_envoy"])
async def test_switch_grid_operation(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_envoy: AsyncMock,
    mock_go_on_grid: AsyncMock,
    mock_go_off_grid: AsyncMock,
) -> None:
    """Test enphase_envoy grid connection operation."""

    await setup_with_selected_platforms(hass, config_entry, [Platform.SWITCH])

    # build switching orders
    INITIAL_OFF_ORDER = (SERVICE_TURN_ON, SERVICE_TURN_OFF, SERVICE_TOGGLE)
    INITIAL_ON_ORDER = (SERVICE_TURN_OFF, SERVICE_TURN_ON, SERVICE_TOGGLE)

    entity_base = f"{Platform.SWITCH}.enpower_"

    if mock_envoy.data.enpower:
        sn = mock_envoy.data.enpower.serial_number
        test_entity = f"{entity_base}{sn}_grid_enabled"
        grid_status = (
            STATE_ON
            if (mock_envoy.data.enpower.mains_admin_state == "closed")
            else STATE_OFF
        )
        # validate envoy value is reflected in entity
        assert grid_status == hass.states.get(test_entity).state

        # test grid status switch change operation
        for option in (
            INITIAL_OFF_ORDER if grid_status == STATE_OFF else INITIAL_ON_ORDER
        ):
            await hass.services.async_call(
                Platform.SWITCH,
                option,
                {ATTR_ENTITY_ID: test_entity},
                blocking=True,
            )
        assert mock_go_on_grid.await_count == (2 if grid_status == STATE_OFF else 1)
        assert mock_go_off_grid.await_count == (2 if grid_status == STATE_ON else 1)


@pytest.mark.parametrize(("mock_envoy"), *ALL_FIXTURES, indirect=["mock_envoy"])
async def test_switch_grid_charge(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_envoy: AsyncMock,
    mock_disable_charge_from_grid: AsyncMock,
    mock_enable_charge_from_grid: AsyncMock,
) -> None:
    """Test enphase_envoy switch charge from grid operation."""

    await setup_with_selected_platforms(hass, config_entry, [Platform.SWITCH])

    # build switching orders
    INITIAL_OFF_ORDER = (SERVICE_TURN_ON, SERVICE_TURN_OFF, SERVICE_TOGGLE)
    INITIAL_ON_ORDER = (SERVICE_TURN_OFF, SERVICE_TURN_ON, SERVICE_TOGGLE)

    entity_base = f"{Platform.SWITCH}.enpower_"

    if (
        mock_envoy.data.tariff
        and mock_envoy.data.tariff.storage_settings
        and mock_envoy.data.enpower
    ):
        sn = mock_envoy.data.enpower.serial_number
        test_entity = f"{entity_base}{sn}_charge_from_grid"
        charge_status = (
            STATE_ON
            if (mock_envoy.data.tariff.storage_settings.charge_from_grid)
            else STATE_OFF
        )
        assert charge_status == hass.states.get(test_entity).state

        # test charge from grid switch change operation
        for option in (
            INITIAL_OFF_ORDER if charge_status == STATE_OFF else INITIAL_ON_ORDER
        ):
            await hass.services.async_call(
                Platform.SWITCH,
                option,
                {ATTR_ENTITY_ID: test_entity},
                blocking=True,
            )

        assert mock_enable_charge_from_grid.await_count == (
            2 if charge_status == STATE_OFF else 1
        )
        assert mock_disable_charge_from_grid.await_count == (
            2 if charge_status == STATE_ON else 1
        )

        mock_enable_charge_from_grid.reset_mock()
        mock_disable_charge_from_grid.reset_mock()


@pytest.mark.parametrize(("mock_envoy"), *ALL_FIXTURES, indirect=["mock_envoy"])
async def test_switch_relay_operation(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_envoy: AsyncMock,
    mock_close_dry_contact: AsyncMock,
    mock_open_dry_contact: AsyncMock,
) -> None:
    """Test enphase_envoy relay entities operation."""

    await setup_with_selected_platforms(hass, config_entry, [Platform.SWITCH])

    # build switching orders
    INITIAL_OFF_ORDER = (SERVICE_TURN_ON, SERVICE_TURN_OFF, SERVICE_TOGGLE)
    INITIAL_ON_ORDER = (SERVICE_TURN_OFF, SERVICE_TURN_ON, SERVICE_TOGGLE)

    entity_base = f"{Platform.SWITCH}."

    if mock_envoy.data.dry_contact_status:
        for id, dry_contact in mock_envoy.data.dry_contact_status.items():
            name = (
                mock_envoy.data.dry_contact_settings[id]
                .load_name.lower()
                .replace(" ", "_")
            )
            test_entity = f"{entity_base}{name}"

            relay_status = (
                STATE_ON
                if (dry_contact.status == DryContactStatus.CLOSED)
                else STATE_OFF
            )
            assert relay_status == hass.states.get(test_entity).state

            # test ralay switch change operations
            for option in (
                INITIAL_OFF_ORDER if relay_status == STATE_OFF else INITIAL_ON_ORDER
            ):
                await hass.services.async_call(
                    Platform.SWITCH,
                    option,
                    {ATTR_ENTITY_ID: test_entity},
                    blocking=True,
                )

            assert mock_close_dry_contact.await_count == (
                2 if relay_status == STATE_OFF else 1
            )
            assert mock_open_dry_contact.await_count == (
                2 if relay_status == STATE_ON else 1
            )

            mock_open_dry_contact.reset_mock()
            mock_close_dry_contact.reset_mock()
