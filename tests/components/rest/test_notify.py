"""The tests for the rest.notify platform."""
from os import path

from homeassistant import config as hass_config
import homeassistant.components.notify as notify
from homeassistant.components.rest import DOMAIN
from homeassistant.const import SERVICE_RELOAD
from homeassistant.setup import async_setup_component

from tests.async_mock import patch


async def test_reload_notify(hass):
    """Verify we can reload the notify service."""

    assert await async_setup_component(
        hass,
        notify.DOMAIN,
        {
            notify.DOMAIN: [
                {
                    "name": DOMAIN,
                    "platform": DOMAIN,
                    "resource": "http://127.0.0.1/off",
                },
            ]
        },
    )
    await hass.async_block_till_done()

    assert hass.services.has_service(notify.DOMAIN, DOMAIN)

    yaml_path = path.join(
        _get_fixtures_base_path(),
        "fixtures",
        "rest/configuration.yaml",
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
    assert hass.services.has_service(notify.DOMAIN, "rest_reloaded")


def _get_fixtures_base_path():
    return path.dirname(path.dirname(path.dirname(__file__)))
