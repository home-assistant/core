"""Test the SFR Box buttons."""

from collections.abc import Generator
from unittest.mock import patch

import pytest
from pytest_homeassistant.common import snapshot_platform
from sfrbox_api.exceptions import SFRBoxAuthenticationError, SFRBoxError
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

pytestmark = pytest.mark.usefixtures(
    "system_get_info", "dsl_get_info", "voip_get_info", "wan_get_info"
)


@pytest.fixture(autouse=True)
def override_platforms() -> Generator[None]:
    """Override PLATFORMS."""
    with (
        patch("homeassistant.components.sfr_box.PLATFORMS", [Platform.BUTTON]),
        patch("homeassistant.components.sfr_box.coordinator.SFRBox.authenticate"),
    ):
        yield


async def test_buttons(
    hass: HomeAssistant,
    config_entry_with_auth: ConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test for SFR Box buttons."""
    await hass.config_entries.async_setup(config_entry_with_auth.entry_id)
    await hass.async_block_till_done()

    await snapshot_platform(
        hass, entity_registry, snapshot, config_entry_with_auth.entry_id
    )


async def test_buttons_no_auth(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test for SFR Box buttons."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Ensure auth-only entities are not registered
    assert len(entity_registry.entities) == 0


async def test_reboot(hass: HomeAssistant, config_entry_with_auth: ConfigEntry) -> None:
    """Test for SFR Box reboot button."""
    await hass.config_entries.async_setup(config_entry_with_auth.entry_id)
    await hass.async_block_till_done()

    # Reboot success
    service_data = {ATTR_ENTITY_ID: "button.sfr_box_restart"}
    with patch(
        "homeassistant.components.sfr_box.button.SFRBox.system_reboot"
    ) as mock_action:
        await hass.services.async_call(
            BUTTON_DOMAIN, SERVICE_PRESS, service_data=service_data, blocking=True
        )

    assert len(mock_action.mock_calls) == 1
    assert mock_action.mock_calls[0][1] == ()

    # Reboot failed
    service_data = {ATTR_ENTITY_ID: "button.sfr_box_restart"}
    with (
        patch(
            "homeassistant.components.sfr_box.button.SFRBox.system_reboot",
            side_effect=SFRBoxError,
        ) as mock_action,
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            BUTTON_DOMAIN, SERVICE_PRESS, service_data=service_data, blocking=True
        )

    assert len(mock_action.mock_calls) == 1
    assert mock_action.mock_calls[0][1] == ()


async def test_reboot_invalid_auth(
    hass: HomeAssistant, config_entry_with_auth: ConfigEntry
) -> None:
    """Test reauthentication is started when credentials fail on press."""
    await hass.config_entries.async_setup(config_entry_with_auth.entry_id)
    await hass.async_block_till_done()

    with (
        patch(
            "homeassistant.components.sfr_box.button.SFRBox.system_reboot",
            side_effect=SFRBoxAuthenticationError,
        ),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            service_data={ATTR_ENTITY_ID: "button.sfr_box_restart"},
            blocking=True,
        )
    await hass.async_block_till_done()

    assert exc_info.value.translation_key == "invalid_credentials"
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == config_entry_with_auth.entry_id
