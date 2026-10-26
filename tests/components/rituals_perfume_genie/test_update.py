"""Tests for the Rituals Perfume Genie update platform."""

from datetime import timedelta
from typing import Any

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import async_fire_time_changed
from ritualsgenie import RitualsGenieResponseError

from homeassistant.components.rituals_perfume_genie.const import DOMAIN
from homeassistant.components.update import (
    ATTR_IN_PROGRESS,
    ATTR_INSTALLED_VERSION,
    ATTR_LATEST_VERSION,
    DOMAIN as UPDATE_DOMAIN,
    SERVICE_INSTALL,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
    EntityCategory,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .common import init_integration, mock_config_entry, mock_diffuser

ENTITY_ID = "update.genie_firmware"


async def _tick(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, delta: timedelta
) -> None:
    """Move the clock forward and let the coordinators update."""
    freezer.tick(delta)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def test_up_to_date(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test the firmware of a diffuser that is up to date."""
    config_entry = mock_config_entry(unique_id="id_123_update_up_to_date")
    await init_integration(hass, config_entry, [mock_diffuser("lot123", version="5.4")])

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_INSTALLED_VERSION] == "5.4 (127)"
    assert state.attributes[ATTR_LATEST_VERSION] == "5.4 (127)"

    entry = entity_registry.async_get(ENTITY_ID)
    assert entry
    assert entry.unique_id == "lot123-firmware"
    assert entry.entity_category is EntityCategory.CONFIG


async def test_update_available_by_firmware_id(hass: HomeAssistant) -> None:
    """Test the firmware IDs tell if an update is available, not the versions."""
    config_entry = mock_config_entry(unique_id="id_123_update_available")
    await init_integration(
        hass,
        config_entry,
        [
            mock_diffuser(
                "lot123",
                version="5.4",
                newest_version="5.4-rc4",
                newest_firmware_id=130,
            )
        ],
    )

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_LATEST_VERSION] == "5.4-rc4 (130)"


async def test_update_same_version_other_build(hass: HomeAssistant) -> None:
    """Test a newer build with the same version can be installed."""
    config_entry = mock_config_entry(unique_id="id_123_update_same_version")
    client = await init_integration(
        hass,
        config_entry,
        [
            mock_diffuser(
                "lot123", version="5.4", newest_version="5.4", newest_firmware_id=130
            )
        ],
    )

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == "5.4 (127)"
    assert state.attributes[ATTR_LATEST_VERSION] == "5.4 (130)"

    await hass.services.async_call(
        UPDATE_DOMAIN, SERVICE_INSTALL, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )

    client.update_firmware.assert_called_once()


async def test_update_available_by_version(hass: HomeAssistant) -> None:
    """Test the versions tell if an update is available, without firmware IDs."""
    config_entry = mock_config_entry(unique_id="id_123_update_by_version")
    await init_integration(
        hass,
        config_entry,
        [
            mock_diffuser(
                "lot123", version="5.4", newest_version="5.5", firmware_id=None
            )
        ],
    )

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_ON


@pytest.mark.parametrize(
    "firmware",
    [{"has_firmware_info": False}, {"version": None}],
    ids=["no_firmware_info", "no_versions"],
)
async def test_no_firmware_info(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, firmware: dict[str, Any]
) -> None:
    """Test a diffuser that doesn't report its firmware."""
    config_entry = mock_config_entry(unique_id="id_123_update_no_firmware")
    await init_integration(hass, config_entry, [mock_diffuser("lot123", **firmware)])
    await _tick(hass, freezer, timedelta(minutes=5))

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_UNKNOWN
    assert state.attributes[ATTR_INSTALLED_VERSION] is None
    assert state.attributes[ATTR_LATEST_VERSION] is None


@pytest.mark.parametrize(
    ("firmware_id", "newest_firmware_id", "installed"),
    [(127, 130, "5.5 (130)"), (None, None, "5.5")],
    ids=["firmware_ids", "versions_only"],
)
async def test_install(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    device_registry: dr.DeviceRegistry,
    firmware_id: int | None,
    newest_firmware_id: int | None,
    installed: str,
) -> None:
    """Test installing firmware, until the diffuser runs it."""
    config_entry = mock_config_entry(unique_id="id_123_update_install")
    diffuser = mock_diffuser(
        "lot123",
        version="5.4",
        firmware_id=firmware_id,
        newest_version="5.5",
        newest_firmware_id=newest_firmware_id,
    )
    client = await init_integration(hass, config_entry, [diffuser])

    await hass.services.async_call(
        UPDATE_DOMAIN, SERVICE_INSTALL, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )

    client.update_firmware.assert_called_once_with(diffuser.hub_hash)
    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.attributes[ATTR_IN_PROGRESS] is True

    # While installing, another install isn't started.
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            UPDATE_DOMAIN, SERVICE_INSTALL, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
        )
    client.update_firmware.assert_called_once()

    # Still the old firmware: still installing.
    await _tick(hass, freezer, timedelta(minutes=5))
    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.attributes[ATTR_IN_PROGRESS] is True

    diffuser.version = "5.5"
    diffuser.firmware_id = newest_firmware_id
    await _tick(hass, freezer, timedelta(minutes=5))

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_IN_PROGRESS] is False
    assert state.attributes[ATTR_INSTALLED_VERSION] == installed

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "lot123"), config_entry.entry_id
    )
    assert device
    assert device.sw_version == "5.5"


async def test_install_timeout(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test an install that never finishes stops being reported."""
    config_entry = mock_config_entry(unique_id="id_123_update_timeout")
    await init_integration(
        hass,
        config_entry,
        [
            mock_diffuser(
                "lot123", version="5.4", newest_version="5.5", newest_firmware_id=130
            )
        ],
    )

    await hass.services.async_call(
        UPDATE_DOMAIN, SERVICE_INSTALL, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )

    await _tick(hass, freezer, timedelta(minutes=30))

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_IN_PROGRESS] is False


async def test_install_incomparable_versions(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test an install keeps going when versions can't be compared."""
    config_entry = mock_config_entry(unique_id="id_123_update_incomparable")
    await init_integration(
        hass,
        config_entry,
        [
            mock_diffuser(
                "lot123", version="5.4", newest_version="build-x", firmware_id=None
            )
        ],
    )

    await hass.services.async_call(
        UPDATE_DOMAIN, SERVICE_INSTALL, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )

    await _tick(hass, freezer, timedelta(minutes=5))

    assert "AwesomeVersionCompareException" not in caplog.text
    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.attributes[ATTR_IN_PROGRESS] is True


async def test_install_failed(hass: HomeAssistant) -> None:
    """Test a failing install is reported, and nothing is installing."""
    config_entry = mock_config_entry(unique_id="id_123_update_failed")
    client = await init_integration(
        hass,
        config_entry,
        [
            mock_diffuser(
                "lot123", version="5.4", newest_version="5.5", newest_firmware_id=130
            )
        ],
    )
    client.update_firmware.side_effect = RitualsGenieResponseError(
        "Already the latest firmware", status=409
    )

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            UPDATE_DOMAIN, SERVICE_INSTALL, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
        )

    assert exc_info.value.translation_key == "firmware_update_failed"
    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.attributes[ATTR_IN_PROGRESS] is False
