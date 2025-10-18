import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from homeassistant.auth.providers import load_auth_provider_module
from homeassistant.core import HomeAssistant


@pytest.mark.asyncio
async def test_load_auth_provider_module_success(hass: HomeAssistant) -> None:
    """Test successful loading of an auth provider with requirements."""
    fake_module = MagicMock()
    fake_module.REQUIREMENTS = ["some-lib"]

    hass.config.skip_pip = False
    hass.data = {}

    with (
        patch(
            "homeassistant.auth.providers.async_import_module",
            return_value=fake_module,
        ) as mock_import,
        patch(
            "homeassistant.requirements.async_process_requirements",
            new_callable=AsyncMock,
        ) as mock_requirements,
    ):
        module = await load_auth_provider_module(hass, "demo")

    mock_import.assert_awaited_once_with(hass, "homeassistant.auth.providers.demo")
    mock_requirements.assert_awaited_once_with(hass, "auth provider demo", ["some-lib"])
    assert module == fake_module
