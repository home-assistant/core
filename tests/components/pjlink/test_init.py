"""Tests for the PJLink integration initialization."""

from unittest.mock import MagicMock, patch

from homeassistant.components.pjlink.const import DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PLATFORM,
    CONF_PORT,
    Platform,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component


async def test_config_import(
    hass: HomeAssistant,
    mock_setup_entry: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test yaml import."""

    with patch(
        "homeassistant.components.pjlink.config_flow.Projector",
        autospec=True,
    ) as mock_projector:
        mock_instance = mock_projector.from_address.return_value
        mock_instance.get_name.return_value = "test name"

        await async_setup_component(
            hass,
            DOMAIN,
            {
                Platform.MEDIA_PLAYER: [
                    {
                        CONF_PLATFORM: DOMAIN,
                        CONF_HOST: "1.1.1.1",
                        CONF_PORT: 4352,
                        CONF_PASSWORD: "test-password",
                    }
                ]
            },
        )

        await hass.async_block_till_done()

    assert len(issue_registry.issues) == 1
    assert (HOMEASSISTANT_DOMAIN, "deprecated_yaml") in issue_registry.issues
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
