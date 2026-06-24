"""Tests for ``async_remove_config_entry_device``.

The "Delete from this integration" link is refused while a device's vehicle is
still in the ``selected ∩ present`` set (selected in ``CONF_VEHICLE_IDS`` AND
live in the garage), and permitted once the vehicle drops out of either — so an
orphaned device card can be cleaned up. A vehicle that is selected but has
vanished from the garage and one that is present but unselected both fall on the
"permitted" side because neither is in ``selected ∩ present``.
"""

from typing import Any

import pytest

from homeassistant.components.abetterrouteplanner.const import CONF_VEHICLE_IDS, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from .conftest import MOCK_VEHICLE_ID, MOCK_VEHICLE_ID_2, SENSOR_TEST_SUB

from tests.common import MockConfigEntry
from tests.typing import WebSocketGenerator

# A vehicle id absent from the 2-vehicle garage (``mock_abrp_vehicles``), used
# for the selected-but-vanished case.
ABSENT_VEHICLE_ID = 123456789


async def _setup_entry(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Register the OAuth implementation and set up the entry."""
    assert await async_setup_component(hass, "auth", {})
    assert await async_setup_component(hass, DOMAIN, {})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("mock_abrp_client", "fake_stream")
@pytest.mark.parametrize(
    ("selected_ids", "device_vehicle_id", "expect_removed"),
    [
        pytest.param(
            [str(MOCK_VEHICLE_ID)],
            MOCK_VEHICLE_ID,
            False,
            id="active_selected_and_present_refused",
        ),
        pytest.param(
            [str(MOCK_VEHICLE_ID)],
            MOCK_VEHICLE_ID_2,
            True,
            id="present_but_unselected_allowed",
        ),
        pytest.param(
            [str(MOCK_VEHICLE_ID), str(ABSENT_VEHICLE_ID)],
            ABSENT_VEHICLE_ID,
            True,
            id="selected_but_vanished_allowed",
        ),
    ],
)
async def test_remove_config_entry_device(
    hass: HomeAssistant,
    token_entry: dict[str, Any],
    device_registry: dr.DeviceRegistry,
    hass_ws_client: WebSocketGenerator,
    selected_ids: list[str],
    device_vehicle_id: int,
    expect_removed: bool,
) -> None:
    """Removal is refused only while the device's vehicle is active."""
    assert await async_setup_component(hass, "config", {})
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=SENSOR_TEST_SUB,
        data={
            "auth_implementation": DOMAIN,
            "token": token_entry,
            CONF_VEHICLE_IDS: selected_ids,
        },
    )
    await _setup_entry(hass, entry)

    # ``async_get_or_create`` is idempotent: for the active vehicle it returns
    # the device the setup anchor already created; for the other cases (not
    # anchored at setup) it materialises the card the test needs to delete.
    scope = f"{entry.unique_id}_{device_vehicle_id}"
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, scope)},
    )

    client = await hass_ws_client(hass)
    response = await client.remove_device(device.id, entry.entry_id)

    assert response["success"] is expect_removed
    assert (
        device_registry.async_get_device(identifiers={(DOMAIN, scope)}) is None
    ) is expect_removed
