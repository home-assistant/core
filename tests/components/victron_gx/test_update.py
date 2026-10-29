"""Tests for Victron GX firmware updates."""

from collections.abc import Callable
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
from victron_mqtt import (
    FirmwareUpdateError,
    FirmwareUpdateErrorReason,
    FirmwareUpdateState,
    Hub as VictronVenusHub,
)
from victron_mqtt.testing import finalize_injection, inject_message

from homeassistant.components.update import (
    ATTR_IN_PROGRESS,
    ATTR_INSTALLED_VERSION,
    ATTR_LATEST_VERSION,
    ATTR_SKIPPED_VERSION,
    ATTR_TITLE,
    ATTR_UPDATE_PERCENTAGE,
    DOMAIN as UPDATE_DOMAIN,
    SERVICE_INSTALL,
    SERVICE_SKIP,
    UpdateDeviceClass,
    UpdateEntityFeature,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    EntityCategory,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .const import MOCK_INSTALLATION_ID


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

    entity = er.async_entries_for_config_entry(entity_registry, config_entry.entry_id)
    update_entry = next(entry for entry in entity if entry.domain == UPDATE_DOMAIN)

    state = hass.states.get(update_entry.entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    await _async_inject_firmware_versions(hass, victron_hub, "v3.80~45", "v3.80~36")

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

    await inject_message(
        victron_hub,
        f"N/{MOCK_INSTALLATION_ID}/platform/0/Firmware/State",
        '{"value": 1000}',
    )
    await finalize_injection(victron_hub)
    await hass.async_block_till_done()

    state = hass.states.get(update_entry.entity_id)
    assert state is not None
    assert state.attributes[ATTR_IN_PROGRESS] is False
    assert state.attributes[ATTR_UPDATE_PERCENTAGE] is None


async def test_firmware_without_available_version(
    hass: HomeAssistant,
    init_integration_with_update: tuple[VictronVenusHub, MockConfigEntry],
    entity_registry: er.EntityRegistry,
) -> None:
    """Test installed firmware remains available without an online version."""
    victron_hub, config_entry = init_integration_with_update
    await inject_message(
        victron_hub,
        f"N/{MOCK_INSTALLATION_ID}/platform/0/Firmware/Installed/Version",
        '{"value": "v3.60"}',
    )
    await finalize_injection(victron_hub)
    await hass.async_block_till_done()

    update_entry = next(
        entry
        for entry in er.async_entries_for_config_entry(
            entity_registry, config_entry.entry_id
        )
        if entry.domain == UPDATE_DOMAIN
    )
    state = hass.states.get(update_entry.entity_id)
    assert state is not None
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_INSTALLED_VERSION] == "v3.60"
    assert state.attributes[ATTR_LATEST_VERSION] == "v3.60"


@pytest.mark.parametrize(
    "firmware_state",
    [
        pytest.param(FirmwareUpdateState.CHECKING, id="checking"),
        pytest.param(FirmwareUpdateState.ERROR_DURING_CHECK, id="check-failed"),
    ],
)
async def test_firmware_check_preserves_skipped_update(
    hass: HomeAssistant,
    init_integration_with_update: tuple[VictronVenusHub, MockConfigEntry],
    entity_registry: er.EntityRegistry,
    firmware_state: FirmwareUpdateState,
) -> None:
    """Test unresolved checks preserve the last offer and skipped version."""
    victron_hub, config_entry = init_integration_with_update
    await _async_inject_firmware_versions(hass, victron_hub, "v3.60", "v3.70")
    update_entry = next(
        entry
        for entry in er.async_entries_for_config_entry(
            entity_registry, config_entry.entry_id
        )
        if entry.domain == UPDATE_DOMAIN
    )
    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_SKIP,
        {ATTR_ENTITY_ID: update_entry.entity_id},
        blocking=True,
    )

    state = hass.states.get(update_entry.entity_id)
    assert state is not None
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_SKIPPED_VERSION] == "v3.70"

    await inject_message(
        victron_hub,
        f"N/{MOCK_INSTALLATION_ID}/platform/0/Firmware/Online/AvailableVersion",
        '{"value": null}',
    )
    await inject_message(
        victron_hub,
        f"N/{MOCK_INSTALLATION_ID}/platform/0/Firmware/State",
        f'{{"value": {firmware_state.code}}}',
    )
    await finalize_injection(victron_hub)
    await hass.async_block_till_done()

    state = hass.states.get(update_entry.entity_id)
    assert state is not None
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_LATEST_VERSION] == "v3.70"
    assert state.attributes[ATTR_SKIPPED_VERSION] == "v3.70"

    await inject_message(
        victron_hub,
        f"N/{MOCK_INSTALLATION_ID}/platform/0/Firmware/State",
        f'{{"value": {FirmwareUpdateState.IDLE.code}}}',
    )
    await _async_inject_firmware_versions(hass, victron_hub, "v3.60", "v3.70")

    state = hass.states.get(update_entry.entity_id)
    assert state is not None
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_SKIPPED_VERSION] == "v3.70"

    await _async_inject_firmware_versions(hass, victron_hub, "v3.60", "v3.80")

    state = hass.states.get(update_entry.entity_id)
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_LATEST_VERSION] == "v3.80"
    assert state.attributes[ATTR_SKIPPED_VERSION] is None


@pytest.mark.parametrize(
    "firmware_state",
    [
        pytest.param(1002, id="downloading-and-installing"),
        pytest.param(1001, id="checking-during-install"),
    ],
)
async def test_install_firmware_update_service(
    hass: HomeAssistant,
    init_integration_with_update: tuple[VictronVenusHub, MockConfigEntry],
    entity_registry: er.EntityRegistry,
    firmware_state: int,
) -> None:
    """Test installation stays in progress across device state changes."""
    victron_hub, config_entry = init_integration_with_update
    await _async_inject_firmware_versions(hass, victron_hub, "v3.60", "v3.70")
    update_entry = next(
        entry
        for entry in er.async_entries_for_config_entry(
            entity_registry, config_entry.entry_id
        )
        if entry.domain == UPDATE_DOMAIN
    )

    async def install_firmware_update(
        progress_callback: Callable[[int], None],
    ) -> None:
        state = hass.states.get(update_entry.entity_id)
        assert state is not None
        assert state.attributes[ATTR_IN_PROGRESS] is True

        progress_callback(42)
        await inject_message(
            victron_hub,
            f"N/{MOCK_INSTALLATION_ID}/platform/0/Firmware/State",
            f'{{"value": {firmware_state}}}',
        )
        await finalize_injection(victron_hub)
        await hass.async_block_till_done()

        state = hass.states.get(update_entry.entity_id)
        assert state is not None
        assert state.attributes[ATTR_IN_PROGRESS] is True
        assert state.attributes[ATTR_UPDATE_PERCENTAGE] == 42

        progress_callback(84)
        state = hass.states.get(update_entry.entity_id)
        assert state is not None
        assert state.attributes[ATTR_IN_PROGRESS] is True
        assert state.attributes[ATTR_UPDATE_PERCENTAGE] == 84

        with pytest.raises(HomeAssistantError) as err:
            await hass.services.async_call(
                UPDATE_DOMAIN,
                SERVICE_INSTALL,
                {ATTR_ENTITY_ID: update_entry.entity_id},
                blocking=True,
            )

        assert err.value.translation_domain == UPDATE_DOMAIN
        assert err.value.translation_key == "update_in_progress"

    with patch.object(
        victron_hub,
        "install_firmware_update",
        new=AsyncMock(side_effect=install_firmware_update),
    ) as install:
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: update_entry.entity_id},
            blocking=True,
        )

    install.assert_awaited_once()
    state = hass.states.get(update_entry.entity_id)
    assert state is not None
    assert state.attributes[ATTR_IN_PROGRESS] is False
    assert state.attributes[ATTR_UPDATE_PERCENTAGE] is None

    await inject_message(
        victron_hub,
        f"N/{MOCK_INSTALLATION_ID}/platform/0/Firmware/State",
        '{"value": 1000}',
    )
    await finalize_injection(victron_hub)
    await hass.async_block_till_done()

    state = hass.states.get(update_entry.entity_id)
    assert state is not None
    assert state.attributes[ATTR_IN_PROGRESS] is False
    assert state.attributes[ATTR_UPDATE_PERCENTAGE] is None


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

    async def install_firmware_update(
        progress_callback: Callable[[int], None],
    ) -> None:
        progress_callback(42)
        state = hass.states.get(update_entry.entity_id)
        assert state is not None
        assert state.attributes[ATTR_IN_PROGRESS] is True
        assert state.attributes[ATTR_UPDATE_PERCENTAGE] == 42
        raise FirmwareUpdateError(FirmwareUpdateErrorReason.ERROR_DURING_UPDATE)

    with (
        patch.object(
            victron_hub,
            "install_firmware_update",
            new=AsyncMock(side_effect=install_firmware_update),
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

    await inject_message(
        victron_hub,
        f"N/{MOCK_INSTALLATION_ID}/platform/0/Firmware/State",
        '{"value": 1001}',
    )
    await finalize_injection(victron_hub)
    await hass.async_block_till_done()

    state = hass.states.get(update_entry.entity_id)
    assert state is not None
    assert state.attributes[ATTR_IN_PROGRESS] is False
    assert state.attributes[ATTR_UPDATE_PERCENTAGE] is None
