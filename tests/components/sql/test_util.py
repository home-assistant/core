"""Test the sql utils."""
from unittest.mock import AsyncMock

from homeassistant.components.recorder import get_instance
from homeassistant.components.sql.util import resolve_db_url
from homeassistant.core import HomeAssistant


async def test_resolve_db_url_when_none_configured(
    recorder_mock: AsyncMock,
    hass: HomeAssistant,
):
    """Test return recorder db_url if provided db_url is None."""
    db_url = None
    resolved_url = resolve_db_url(hass, db_url)

    assert resolved_url == get_instance(hass).db_url


async def test_resolve_db_url_when_configured(hass: HomeAssistant):
    """Test return provided db_url if it's set."""
    db_url = "mssql://"
    resolved_url = resolve_db_url(hass, db_url)

    assert resolved_url == db_url
