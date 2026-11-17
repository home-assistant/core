"""Tests for Daikin Onecta refresh button entities."""

from unittest.mock import AsyncMock

from daikin_onecta.exceptions import OnectaConnectionError
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .platform_helpers import _async_fire_coordinator_update
from .test_climate_snapshots import _async_setup_fixture, _load_gateway_devices


async def test_refresh_button_requests_coordinator_refresh(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """The refresh button requests one coordinator refresh."""
    await _async_setup_fixture(hass, config_entry, "dry")
    coordinator = config_entry.runtime_data
    coordinator.async_refresh = AsyncMock()

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.daikin_onecta_account_refresh"},
        blocking=True,
    )

    coordinator.async_refresh.assert_awaited_once()


async def test_refresh_button_reports_failed_refresh(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """A failed cloud refresh is reported to the service caller."""
    await _async_setup_fixture(hass, config_entry, "dry")
    coordinator = config_entry.runtime_data

    async def fail_refresh() -> None:
        coordinator.last_update_success = False

    coordinator.async_refresh = AsyncMock(side_effect=fail_refresh)

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.daikin_onecta_account_refresh"},
            blocking=True,
        )

    assert err.value.translation_domain == "daikin_onecta"
    assert err.value.translation_key == "refresh_failed"
    assert err.value.translation_placeholders is None
    coordinator.async_refresh.assert_awaited_once()


async def test_refresh_button_recovers_after_failed_poll(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    mock_onecta_client,
) -> None:
    """Keep the button usable to retry a failed poll without reloading."""
    await _async_setup_fixture(hass, config_entry, "dry")
    coordinator = config_entry.runtime_data
    mock_onecta_client.get_gateway_devices.side_effect = OnectaConnectionError(
        "network unavailable", method="GET", path="/v1/gateway-devices"
    )
    await _async_fire_coordinator_update(hass, coordinator, freezer)
    assert not coordinator.last_update_success
    state = hass.states.get("button.daikin_onecta_account_refresh")
    assert state is not None
    assert state.state != "unavailable"

    mock_onecta_client.get_gateway_devices.side_effect = None
    mock_onecta_client.get_gateway_devices.return_value = _load_gateway_devices("dry")
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.daikin_onecta_account_refresh"},
        blocking=True,
    )

    assert coordinator.last_update_success
    mock_onecta_client.get_gateway_devices.assert_awaited()
