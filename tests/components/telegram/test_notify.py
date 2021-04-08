"""The tests for the telegram.notify platform."""
from os import path
from unittest.mock import patch

from homeassistant import config as hass_config
import homeassistant.components.notify as notify
from homeassistant.components.telegram import DOMAIN
from homeassistant.const import SERVICE_RELOAD
from homeassistant.setup import async_setup_component


async def test_reload_notify(hass):
    """Verify we can reload the notify service."""

    with patch("homeassistant.components.telegram_bot.async_setup", return_value=True):
        assert await async_setup_component(
            hass,
            notify.DOMAIN,
            {
                notify.DOMAIN: [
                    {
                        "name": DOMAIN,
                        "platform": DOMAIN,
                        "chat_id": 1,
                    },
                ]
            },
        )
        await hass.async_block_till_done()

    assert hass.services.has_service(notify.DOMAIN, DOMAIN)

    yaml_path = path.join(
        _get_fixtures_base_path(),
        "fixtures",
        "telegram/configuration.yaml",
    )
    with patch.object(hass_config, "YAML_CONFIG_FILE", yaml_path):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RELOAD,
            {},
            blocking=True,
        )
        await hass.async_block_till_done()

    assert not hass.services.has_service(notify.DOMAIN, DOMAIN)
    assert hass.services.has_service(notify.DOMAIN, "telegram_reloaded")


def _get_fixtures_base_path():
    return path.dirname(path.dirname(path.dirname(__file__)))
