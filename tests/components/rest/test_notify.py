"""The tests for the rest.notify platform."""
from unittest.mock import patch

import respx

from homeassistant import config as hass_config
import homeassistant.components.notify as notify
from homeassistant.components.rest import DOMAIN
from homeassistant.const import SERVICE_RELOAD
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from tests.common import get_fixture_path


@respx.mock
async def test_reload_notify(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Verify we can reload the notify service."""
    respx.get("http://localhost") % 200

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
    assert issue_registry.async_get_issue(DOMAIN, "deprecated_platform_yaml")

    assert hass.services.has_service(notify.DOMAIN, DOMAIN)

    yaml_path = get_fixture_path("configuration.yaml", "rest")

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
