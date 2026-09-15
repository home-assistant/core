"""Test administrative OpenGarage actions."""

from unittest.mock import MagicMock

import pytest

from homeassistant.const import ATTR_CONFIG_ENTRY_ID
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import (
    HomeAssistantError,
    ServiceValidationError,
    Unauthorized,
)

from tests.common import MockConfigEntry, MockUser


async def test_reset_wifi(
    hass: HomeAssistant,
    mock_opengarage: MagicMock,
    init_integration: MockConfigEntry,
    hass_admin_user: MockUser,
) -> None:
    """An administrator can put the selected device in AP mode."""
    mock_opengarage.ap_mode.return_value = 1
    await hass.services.async_call(
        "opengarage",
        "reset_wifi",
        {ATTR_CONFIG_ENTRY_ID: init_integration.entry_id},
        blocking=True,
        context=Context(user_id=hass_admin_user.id),
    )
    mock_opengarage.ap_mode.assert_awaited_once_with()


async def test_reset_wifi_non_admin(
    hass: HomeAssistant,
    mock_opengarage: MagicMock,
    init_integration: MockConfigEntry,
    hass_read_only_user: MockUser,
) -> None:
    """Reject non-admin callers before issuing any command."""
    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            "opengarage",
            "reset_wifi",
            {ATTR_CONFIG_ENTRY_ID: init_integration.entry_id},
            blocking=True,
            context=Context(user_id=hass_read_only_user.id),
        )
    mock_opengarage.ap_mode.assert_not_called()


@pytest.mark.parametrize(
    "result",
    [
        pytest.param(None, id="missing"),
        pytest.param(2, id="bad_key"),
        pytest.param(99, id="error"),
    ],
)
async def test_reset_wifi_failure(
    hass: HomeAssistant,
    mock_opengarage: MagicMock,
    init_integration: MockConfigEntry,
    result: int | None,
) -> None:
    """Report unsuccessful resets instead of silently accepting them."""
    mock_opengarage.ap_mode.return_value = result
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "opengarage",
            "reset_wifi",
            {ATTR_CONFIG_ENTRY_ID: init_integration.entry_id},
            blocking=True,
        )


async def test_reset_wifi_unloaded(
    hass: HomeAssistant, mock_opengarage: MagicMock, init_integration: MockConfigEntry
) -> None:
    """A stale config entry selection cannot call an unloaded client."""
    assert await hass.config_entries.async_unload(init_integration.entry_id)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            "opengarage",
            "reset_wifi",
            {ATTR_CONFIG_ENTRY_ID: init_integration.entry_id},
            blocking=True,
        )
    mock_opengarage.ap_mode.assert_not_called()
