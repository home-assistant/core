"""Tests for Victron GX firmware updates."""

from collections.abc import Callable
from unittest.mock import AsyncMock, MagicMock, patch

from victron_mqtt import (
    FirmwareUpdateError,
    FirmwareUpdateErrorReason,
    FirmwareUpdateInfo,
    FirmwareUpdateState,
    Hub as VictronVenusHub,
)
from victron_mqtt.testing import finalize_injection, inject_message

from homeassistant.components.update import (
    ATTR_IN_PROGRESS,
    ATTR_INSTALLED_VERSION,
    ATTR_LATEST_VERSION,
    ATTR_UPDATE_PERCENTAGE,
    DOMAIN as UPDATE_DOMAIN,
    SERVICE_INSTALL,
    UpdateDeviceClass,
    UpdateEntityFeature,
)
from homeassistant.components.victron_gx.hub import Hub
from homeassistant.components.victron_gx.update import VictronFirmwareUpdateEntity
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_component import async_update_entity

from .const import MOCK_INSTALLATION_ID

from tests.common import MockConfigEntry


def _create_update_entity(
    installed: str | None = "v3.60", available: str | None = "v3.70"
) -> tuple[VictronFirmwareUpdateEntity, MagicMock]:
    """Create a firmware update entity backed by a mocked hub."""
    entry = MockConfigEntry(domain="victron_gx", unique_id=MOCK_INSTALLATION_ID)
    hub = MagicMock(spec=Hub)
    hub.firmware_update_info = FirmwareUpdateInfo(
        installed, available, FirmwareUpdateState.IDLE, None
    )
    hub.install_firmware_update = AsyncMock()
    entry.runtime_data = hub
    return VictronFirmwareUpdateEntity(entry), hub


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
    await async_update_entity(hass, update_entry.entity_id)

    state = hass.states.get(update_entry.entity_id)
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_DEVICE_CLASS] == UpdateDeviceClass.FIRMWARE
    assert state.attributes[ATTR_INSTALLED_VERSION] == "v3.80~45"
    assert state.attributes[ATTR_LATEST_VERSION] == "v3.80~36"
    assert state.attributes[ATTR_IN_PROGRESS] is False
    assert state.attributes[ATTR_UPDATE_PERCENTAGE] is None
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == (
        UpdateEntityFeature.INSTALL | UpdateEntityFeature.PROGRESS
    )


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
    await async_update_entity(hass, update_entry.entity_id)

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


async def test_install_does_not_start_without_available_version() -> None:
    """Test installation does not start without a firmware offer."""
    entity, hub = _create_update_entity(available=None)
    entity.hass = MagicMock()

    await entity.async_install(None, False)

    assert entity.latest_version == "v3.60"
    hub.install_firmware_update.assert_not_called()


async def test_install_updates_progress_and_clears_failure() -> None:
    """Test progress is published and cleared after a handled GX failure."""
    entity, hub = _create_update_entity()
    entity.hass = MagicMock()
    states: list[tuple[bool | None, int | float | None]] = []

    async def install(update_progress: Callable[[int], None]) -> None:
        update_progress(25)
        raise FirmwareUpdateError(FirmwareUpdateErrorReason.ERROR_DURING_UPDATE)

    with (
        patch.object(hub, "install_firmware_update", side_effect=install),
        patch.object(
            entity,
            "async_write_ha_state",
            side_effect=lambda: states.append(
                (entity.in_progress, entity.update_percentage)
            ),
        ),
    ):
        await entity.async_install(None, False)

    assert states == [(True, None), (True, 25), (False, None)]


async def test_update_refreshes_install_progress() -> None:
    """Test polling refreshes progress from the library snapshot."""
    entity, hub = _create_update_entity()
    hub.firmware_update_info = FirmwareUpdateInfo(
        "v3.60",
        "v3.70",
        FirmwareUpdateState.DOWNLOADING_AND_INSTALLING,
        25,
    )

    await entity.async_update()

    assert entity.in_progress is True
    assert entity.update_percentage == 25
