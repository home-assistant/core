"""Tests for Victron GX firmware updates."""

from unittest.mock import AsyncMock, patch

import pytest
from victron_mqtt import (
    FirmwareUpdateError,
    FirmwareUpdateErrorReason,
    Hub as VictronVenusHub,
)
from victron_mqtt.testing import finalize_injection, inject_message

from homeassistant.components.update import (
    ATTR_IN_PROGRESS,
    ATTR_INSTALLED_VERSION,
    ATTR_LATEST_VERSION,
    ATTR_TITLE,
    ATTR_UPDATE_PERCENTAGE,
    DOMAIN as UPDATE_DOMAIN,
    SERVICE_INSTALL,
    UpdateDeviceClass,
    UpdateEntityFeature,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    STATE_ON,
    EntityCategory,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .const import MOCK_INSTALLATION_ID

from tests.common import MockConfigEntry


async def _async_inject_firmware_versions(
    hass: HomeAssistant,
    victron_hub: VictronVenusHub,
    installed: str,
    available: str,
) -> None:
    """Inject installed and available firmware versions."""
    await inject_message(
        victron_hub,
        f"N/{MOCK_INSTALLATION_ID}/platform/0/Firmware/Installed/Version",
        f'{{"value": "{installed}"}}',
    )
    await inject_message(
        victron_hub,
        f"N/{MOCK_INSTALLATION_ID}/platform/0/Firmware/Online/AvailableVersion",
        f'{{"value": "{available}"}}',
    )
    await finalize_injection(victron_hub)
    await hass.async_block_till_done()


async def test_firmware_update_entity(
    hass: HomeAssistant,
    init_integration_with_update: tuple[VictronVenusHub, MockConfigEntry],
    entity_registry: er.EntityRegistry,
) -> None:
    """Test firmware versions create an available update."""
    victron_hub, config_entry = init_integration_with_update
    await _async_inject_firmware_versions(hass, victron_hub, "v3.80~45", "v3.80~36")

    entity = er.async_entries_for_config_entry(entity_registry, config_entry.entry_id)
    update_entry = next(entry for entry in entity if entry.domain == UPDATE_DOMAIN)

    state = hass.states.get(update_entry.entity_id)
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_DEVICE_CLASS] == UpdateDeviceClass.FIRMWARE
    assert update_entry.entity_category is EntityCategory.CONFIG
    assert update_entry.translation_key is None
    assert state.attributes[ATTR_TITLE] == "Venus OS"
    assert state.attributes[ATTR_INSTALLED_VERSION] == "v3.80~45"
    assert state.attributes[ATTR_LATEST_VERSION] == "v3.80~36"
    assert state.attributes[ATTR_IN_PROGRESS] is False
    assert state.attributes[ATTR_UPDATE_PERCENTAGE] is None
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == (
        UpdateEntityFeature.INSTALL | UpdateEntityFeature.PROGRESS
    )

    await inject_message(
        victron_hub,
        f"N/{MOCK_INSTALLATION_ID}/platform/0/Firmware/State",
        '{"value": 1002}',
    )
    await inject_message(
        victron_hub,
        f"N/{MOCK_INSTALLATION_ID}/platform/0/Firmware/Progress",
        '{"value": 25}',
    )
    await finalize_injection(victron_hub)
    await hass.async_block_till_done()

    state = hass.states.get(update_entry.entity_id)
    assert state is not None
    assert state.attributes[ATTR_IN_PROGRESS] is True
    assert state.attributes[ATTR_UPDATE_PERCENTAGE] == 25


async def test_install_firmware_update_service(
    hass: HomeAssistant,
    init_integration_with_update: tuple[VictronVenusHub, MockConfigEntry],
    entity_registry: er.EntityRegistry,
) -> None:
    """Test installing the firmware offered by the GX device."""
    victron_hub, config_entry = init_integration_with_update
    await _async_inject_firmware_versions(hass, victron_hub, "v3.60", "v3.70")
    update_entry = next(
        entry
        for entry in er.async_entries_for_config_entry(
            entity_registry, config_entry.entry_id
        )
        if entry.domain == UPDATE_DOMAIN
    )

    with patch.object(
        config_entry.runtime_data,
        "install_firmware_update",
        new=AsyncMock(),
    ) as install:
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: update_entry.entity_id},
            blocking=True,
        )

    install.assert_awaited_once()
    assert install.await_args is not None
    assert callable(install.await_args.args[0])


async def test_install_propagates_translated_failure_and_clears_progress(
    hass: HomeAssistant,
    init_integration_with_update: tuple[VictronVenusHub, MockConfigEntry],
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a GX failure is translated and install progress is cleared."""
    victron_hub, config_entry = init_integration_with_update
    await _async_inject_firmware_versions(hass, victron_hub, "v3.60", "v3.70")
    update_entry = next(
        entry
        for entry in er.async_entries_for_config_entry(
            entity_registry, config_entry.entry_id
        )
        if entry.domain == UPDATE_DOMAIN
    )

    with (
        patch.object(
            config_entry.runtime_data,
            "install_firmware_update",
            new=AsyncMock(
                side_effect=FirmwareUpdateError(
                    FirmwareUpdateErrorReason.ERROR_DURING_UPDATE
                )
            ),
        ),
        pytest.raises(HomeAssistantError) as err,
    ):
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: update_entry.entity_id},
            blocking=True,
        )

    assert err.value.translation_domain == "victron_gx"
    assert err.value.translation_key == "error_during_update"
    state = hass.states.get(update_entry.entity_id)
    assert state is not None
    assert state.attributes[ATTR_IN_PROGRESS] is False
    assert state.attributes[ATTR_UPDATE_PERCENTAGE] is None
