"""Tensorflow test."""

from unittest.mock import Mock, patch

from homeassistant.components.image_processing import DOMAIN as IMAGE_PROCESSING_DOMAINN
from homeassistant.components.tensorflow import CONF_GRAPH, DOMAIN
from homeassistant.const import CONF_ENTITY_ID, CONF_MODEL, CONF_PLATFORM, CONF_SOURCE
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component


@patch.dict("sys.modules", tensorflow=Mock())
async def test_repair_issue_is_created(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test repair issue is created."""
    assert await async_setup_component(
        hass,
        IMAGE_PROCESSING_DOMAINN,
        {
            IMAGE_PROCESSING_DOMAINN: [
                {
                    CONF_PLATFORM: DOMAIN,
                    CONF_SOURCE: [
                        {CONF_ENTITY_ID: "camera.test_camera"},
                    ],
                    CONF_MODEL: {
                        CONF_GRAPH: ".",
                    },
                }
            ],
        },
    )
    await hass.async_block_till_done()
    assert (
        HOMEASSISTANT_DOMAIN,
        f"deprecated_system_packages_yaml_integration_{DOMAIN}",
    ) in issue_registry.issues
