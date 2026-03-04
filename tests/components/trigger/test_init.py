"""Test trigger integration setup."""

from unittest.mock import AsyncMock, patch

from homeassistant.components.trigger import DEFAULT_TRIGGER_DOMAINS
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


async def test_setup_registers_trigger_platform(hass: HomeAssistant) -> None:
    """Test that setup registers trigger platforms from available integrations."""
    mock_platform = AsyncMock()
    mock_integration = AsyncMock(
        async_get_platform=AsyncMock(return_value=mock_platform),
    )

    with (
        patch(
            "homeassistant.components.trigger.async_get_integration",
            return_value=mock_integration,
        ),
        patch(
            "homeassistant.components.trigger.async_register_trigger_platform",
        ) as mock_register,
    ):
        assert await async_setup_component(hass, "trigger", {})

        assert mock_register.call_count == len(DEFAULT_TRIGGER_DOMAINS)
        for domain in DEFAULT_TRIGGER_DOMAINS:
            mock_register.assert_any_call(hass, domain, mock_platform)


async def test_setup_skips_missing_integrations(hass: HomeAssistant) -> None:
    """Test that setup skips integrations that don't exist."""
    with (
        patch(
            "homeassistant.components.trigger.DEFAULT_TRIGGER_DOMAINS",
            ("non_existent",),
        ),
        patch(
            "homeassistant.components.trigger.async_register_trigger_platform",
        ) as mock_register,
    ):
        assert await async_setup_component(hass, "trigger", {})
        mock_register.assert_not_called()


async def test_setup_skips_integrations_without_trigger_platform(
    hass: HomeAssistant,
) -> None:
    """Test that setup skips integrations without a trigger platform."""
    mock_integration = AsyncMock(
        async_get_platform=AsyncMock(side_effect=ImportError),
    )
    with (
        patch(
            "homeassistant.components.trigger.async_get_integration",
            return_value=mock_integration,
        ),
        patch(
            "homeassistant.components.trigger.async_register_trigger_platform",
        ) as mock_register,
    ):
        assert await async_setup_component(hass, "trigger", {})
        mock_integration.async_get_platform.assert_called_with("trigger")
        mock_register.assert_not_called()
