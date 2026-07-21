"""Test Enphase Envoy button platform."""

from unittest.mock import AsyncMock, patch

from pyenphase.exceptions import EnvoyError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.enphase_envoy.const import Platform
from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform

SLEEP = "button.acb_1234_sleep"
WAKE = "button.acb_1234_wake"
ALL_SERIALS = ["121000000001", "122000000002"]


@pytest.mark.parametrize("mock_envoy", ["envoy_acb_batt"], indirect=True)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_button(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test button platform entities against snapshot."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.BUTTON]):
        await setup_integration(hass, config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.parametrize(
    "mock_envoy",
    [
        "envoy",
        "envoy_1p_metered",
        "envoy_nobatt_metered_3p",
        "envoy_tot_cons_metered",
        "envoy_eu_batt",
    ],
    indirect=True,
)
async def test_no_button(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test button platform entities are not created without ACB batteries."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.BUTTON]):
        await setup_integration(hass, config_entry)
    assert not er.async_entries_for_config_entry(entity_registry, config_entry.entry_id)


@pytest.mark.parametrize("mock_envoy", ["envoy_acb_batt"], indirect=True)
async def test_button_sleep(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test the sleep button calls set_acb_sleep for all batteries."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.BUTTON]):
        await setup_integration(hass, config_entry)

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: SLEEP},
        blocking=True,
    )
    # Default SOC band is derived from the battery configured with sleep thresholds
    mock_envoy.set_acb_sleep.assert_awaited_once_with(
        [
            {"serial_num": serial, "sleep_min_soc": 25, "sleep_max_soc": 30}
            for serial in ALL_SERIALS
        ]
    )


@pytest.mark.parametrize("mock_envoy", ["envoy_acb_batt"], indirect=True)
async def test_button_wake(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test the wake button calls clear_acb_sleep for all batteries."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.BUTTON]):
        await setup_integration(hass, config_entry)

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: WAKE},
        blocking=True,
    )
    mock_envoy.clear_acb_sleep.assert_awaited_once_with(ALL_SERIALS)


@pytest.mark.parametrize("mock_envoy", ["envoy_acb_batt"], indirect=True)
async def test_button_sleep_uses_selected_soc(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test the sleep button applies the SOC band chosen in the select entity."""
    with patch(
        "homeassistant.components.enphase_envoy.PLATFORMS",
        [Platform.BUTTON, Platform.SELECT],
    ):
        await setup_integration(hass, config_entry)

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: "select.acb_1234_battery_sleep_soc_target",
            ATTR_OPTION: "50-55",
        },
        blocking=True,
    )
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: SLEEP},
        blocking=True,
    )
    mock_envoy.set_acb_sleep.assert_awaited_once_with(
        [
            {"serial_num": serial, "sleep_min_soc": 50, "sleep_max_soc": 55}
            for serial in ALL_SERIALS
        ]
    )


@pytest.mark.parametrize("mock_envoy", ["envoy_acb_batt"], indirect=True)
async def test_button_error(
    hass: HomeAssistant,
    mock_envoy: AsyncMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test button press surfaces Envoy errors as HomeAssistantError."""
    with patch("homeassistant.components.enphase_envoy.PLATFORMS", [Platform.BUTTON]):
        await setup_integration(hass, config_entry)

    mock_envoy.set_acb_sleep.side_effect = EnvoyError("Test")
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: SLEEP},
            blocking=True,
        )
