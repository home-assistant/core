"""Test Home Connect application credentials."""

import pytest

from homeassistant.components.home_connect.application_credentials import (
    async_get_description_placeholders,
)
from homeassistant.core import HomeAssistant


@pytest.mark.parametrize(
    ("country", "domain"),
    [
        pytest.param("CN", "developer.home-connect.cn", id="china"),
        pytest.param("ES", "developer.home-connect.com", id="spain"),
        pytest.param(None, "developer.home-connect.com", id="no_country"),
    ],
)
async def test_description_placeholders(
    hass: HomeAssistant, country: str | None, domain: str
) -> None:
    """Test description placeholders use the region specific developer portal."""
    hass.config.country = country
    assert await async_get_description_placeholders(hass) == {
        "developer_dashboard_url": f"https://{domain}/",
        "applications_url": f"https://{domain}/applications",
        "register_application_url": f"https://{domain}/application/add",
        "redirect_url": "https://my.home-assistant.io/redirect/oauth",
    }
