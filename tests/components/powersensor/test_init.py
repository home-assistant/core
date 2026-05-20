"""Tests for initial setup, migration, and teardown of the Powersensor component."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.powersensor import (
    async_migrate_entry,
    async_setup_entry,
    async_unload_entry,
)
from homeassistant.components.powersensor.config_flow import PowersensorConfigFlow
from homeassistant.components.powersensor.const import DOMAIN
from homeassistant.components.powersensor.models import PowersensorRuntimeData
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.loader import (
    DATA_COMPONENTS,
    DATA_INTEGRATIONS,
    DATA_MISSING_PLATFORMS,
    DATA_PRELOAD_PLATFORMS,
)
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

MAC = "a4cf1218f158"


@pytest.fixture
def hass_data(hass: HomeAssistant):
    """Populate hass.data with the loader keys required by async_setup_component."""
    hass.data = {
        DATA_COMPONENTS: {},
        DATA_INTEGRATIONS: {},
        DATA_MISSING_PLATFORMS: {},
        DATA_PRELOAD_PLATFORMS: [],
    }


async def test_async_setup(hass: HomeAssistant, hass_data) -> None:
    """Test that the component loads without error."""
    assert await async_setup_component(hass, DOMAIN, {}) is True


async def test_setup_entry_malformed_device_raises_config_entry_not_ready(
    hass: HomeAssistant,
    hass_data,
) -> None:
    """Test that a malformed device dict in entry.data raises ConfigEntryNotReady.

    Lines 72-73 of __init__.py catch any Exception raised inside the setup
    try-block and re-raise it as ConfigEntryNotReady.  A missing required key
    ('host' here) in a device dict is the most natural trigger — it causes a
    KeyError inside enqueue_plug_for_adding without requiring any library mocks.
    """
    bad_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "devices": {
                "0123456789ab": {
                    "mac": MAC,
                    # "host" intentionally omitted to trigger KeyError
                    "port": 49476,
                    "name": "test-plug",
                }
            },
            "roles": {},
        },
        entry_id="test_malformed",
        version=PowersensorConfigFlow.VERSION,
        minor_version=PowersensorConfigFlow.MINOR_VERSION,
    )

    with pytest.raises(ConfigEntryNotReady) as excinfo:
        await async_setup_entry(hass, bad_entry)

    assert "Unexpected error during setup" in str(excinfo.value)


async def test_migrate_entry(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test config-entry migration from v1 to the current version.

    Verifies that:
    - A v1 entry is migrated to the current version with 'devices' and 'roles' keys.
    - An entry at a higher version than current is rejected (returns False).
    """
    updated = False

    def verify_new_entry(config_entry, data, version, minor_version) -> None:
        nonlocal updated
        updated = True
        assert version == PowersensorConfigFlow.VERSION
        assert minor_version == 2
        assert "devices" in data
        assert "roles" in data

    monkeypatch.setattr(hass.config_entries, "async_update_entry", verify_new_entry)

    old_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"0123456789ab": {}},
        entry_id="test",
        version=1,
        minor_version=1,
    )
    assert await async_migrate_entry(hass, old_entry) is True
    assert updated

    new_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"0123456789ab": {}},
        entry_id="test",
        version=PowersensorConfigFlow.VERSION + 1,
        minor_version=1,
    )
    updated = False
    assert await async_migrate_entry(hass, new_entry) is False
    assert not updated


async def test_setup_unload_entry(
    hass: HomeAssistant,
    hass_data,
    def_config_entry,
) -> None:
    """Test that setup populates hass.data and unload cleans it up."""
    mock_zc = AsyncMock()
    mock_zc.async_close = AsyncMock()
    mock_zc.loop = MagicMock()
    mock_zc.loop.is_running.return_value = True

    with (
        patch(
            "homeassistant.components.zeroconf.async_get_instance",
            return_value=mock_zc,
        ),
        patch(
            "homeassistant.components.powersensor.powersensor_discovery_service.ServiceBrowser",
            MagicMock(),
        ),
    ):
        assert await async_setup_entry(hass, def_config_entry)
        assert hasattr(def_config_entry, "runtime_data")
        assert isinstance(def_config_entry.runtime_data, PowersensorRuntimeData)

        assert await async_unload_entry(hass, def_config_entry)


async def test_setup_exception(
    hass: HomeAssistant,
    hass_data,
    def_config_entry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that a RuntimeError during discovery.start() raises ConfigEntryNotReady.

    Verifies that:
    - ConfigEntryNotReady is raised with the original error message.
    - stop() is called on the discovery service to avoid a resource leak.
    """
    errkey = "Forced start failure"
    stop_called = []

    async def fail_start(self):
        raise RuntimeError(errkey)

    async def record_stop(self):
        stop_called.append(True)

    monkeypatch.setattr(
        "homeassistant.components.powersensor.powersensor_discovery_service.PowersensorDiscoveryService.start",
        fail_start,
    )
    monkeypatch.setattr(
        "homeassistant.components.powersensor.powersensor_discovery_service.PowersensorDiscoveryService.stop",
        record_stop,
    )
    with pytest.raises(ConfigEntryNotReady) as excinfo:
        await async_setup_entry(hass, def_config_entry)

    assert errkey in str(excinfo.value)
    assert stop_called, "stop() must be called to clean up after a failed start()"
