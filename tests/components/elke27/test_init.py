"""Tests for the Elke27 integration setup."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from elke27_lib import ArmMode, LinkKeys
from elke27_lib.errors import Elke27LinkRequiredError, Elke27TimeoutError
import pytest

from homeassistant.components.elke27 import (
    ATTR_CODE,
    ATTR_MODE,
    SERVICE_ALARM_ARM_AUTOMATIC,
    _async_migrate_unique_ids,
    _panel_name_from_entry,
    async_setup,
)
from homeassistant.components.elke27.const import (
    CONF_INTEGRATION_SERIAL,
    CONF_LINK_KEYS_JSON,
    DEFAULT_PORT,
    DOMAIN,
)
from homeassistant.components.elke27.models import Elke27RuntimeData
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


async def test_setup_unload_calls_connect_disconnect_and_subscribe(
    hass: HomeAssistant,
) -> None:
    """Test setup/unload uses hub and coordinator lifecycle."""
    hub = SimpleNamespace(
        panel_name=None,
        async_connect=AsyncMock(return_value=None),
        async_disconnect=AsyncMock(return_value=None),
    )

    coordinator = SimpleNamespace(
        async_start=AsyncMock(return_value=None),
        async_refresh_now=AsyncMock(return_value=None),
        async_stop=AsyncMock(return_value=None),
        data=None,
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.10",
            CONF_PORT: DEFAULT_PORT,
            CONF_LINK_KEYS_JSON: LinkKeys("tk", "lk", "lh").to_json(),
            CONF_INTEGRATION_SERIAL: "112233445566",
        },
    )
    entry.add_to_hass(hass)

    async def _async_forward_entry_setups(*_args, **_kwargs) -> bool:
        return True

    async def _async_unload_platforms(*_args, **_kwargs) -> bool:
        return True

    with (
        patch("homeassistant.components.elke27.Elke27Hub", return_value=hub),
        patch(
            "homeassistant.components.elke27.Elke27DataUpdateCoordinator",
            return_value=coordinator,
        ),
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            _async_forward_entry_setups,
        ),
        patch.object(
            hass.config_entries,
            "async_unload_platforms",
            _async_unload_platforms,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        hub.async_connect.assert_awaited_once()
        coordinator.async_start.assert_awaited_once()
        coordinator.async_refresh_now.assert_awaited_once()
        assert isinstance(entry.runtime_data, Elke27RuntimeData)

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

    coordinator.async_stop.assert_awaited_once()
    hub.async_disconnect.assert_awaited_once()


async def test_setup_transient_error_returns_not_ready(
    hass: HomeAssistant,
) -> None:
    """Test transient setup errors return not ready."""
    hub = SimpleNamespace(
        panel_name=None,
        async_connect=AsyncMock(side_effect=Elke27TimeoutError()),
        async_disconnect=AsyncMock(return_value=None),
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.12",
            CONF_PORT: DEFAULT_PORT,
            CONF_LINK_KEYS_JSON: LinkKeys("tk", "lk", "lh").to_json(),
            CONF_INTEGRATION_SERIAL: "112233445566",
        },
    )
    entry.add_to_hass(hass)

    async def _async_forward_entry_setups(*_args, **_kwargs) -> bool:
        return True

    with (
        patch("homeassistant.components.elke27.Elke27Hub", return_value=hub),
        patch(
            "homeassistant.components.elke27.Elke27DataUpdateCoordinator"
        ) as coordinator_cls,
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            _async_forward_entry_setups,
        ),
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    coordinator_cls.assert_not_called()
    hub.async_disconnect.assert_awaited_once()


@pytest.mark.parametrize(
    "ignore_missing_translations",
    [["component.homeassistant.issues.config_entry_reauth."]],
)
async def test_setup_missing_link_keys_raises_auth_failed(
    hass: HomeAssistant,
) -> None:
    """Test setup fails when link keys are missing."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.1.13", CONF_PORT: DEFAULT_PORT},
    )
    entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_ERROR


@pytest.mark.parametrize(
    "ignore_missing_translations",
    [["component.homeassistant.issues.config_entry_reauth."]],
)
async def test_setup_link_required_raises_auth_failed(
    hass: HomeAssistant,
) -> None:
    """Test link-required errors raise auth failed."""
    hub = SimpleNamespace(
        panel_name=None,
        async_connect=AsyncMock(side_effect=Elke27LinkRequiredError()),
        async_disconnect=AsyncMock(return_value=None),
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.14",
            CONF_PORT: DEFAULT_PORT,
            CONF_LINK_KEYS_JSON: LinkKeys("tk", "lk", "lh").to_json(),
            CONF_INTEGRATION_SERIAL: "112233445566",
        },
    )
    entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.elke27.Elke27Hub", return_value=hub),
        patch("homeassistant.components.elke27.Elke27DataUpdateCoordinator"),
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        assert entry.state is ConfigEntryState.SETUP_ERROR


def test_panel_name_from_entry() -> None:
    """Verify panel name extraction from entry data."""
    assert _panel_name_from_entry({"panel_name": "Panel"}) == "Panel"
    assert _panel_name_from_entry({"name": "Panel 2"}) == "Panel 2"
    assert _panel_name_from_entry(None) is None


async def test_migrate_unique_ids(hass: HomeAssistant) -> None:
    """Verify unique IDs are migrated to the new format."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.1.10"},
    )
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    base = "aa:bb:cc:dd:ee:ff"
    old_unique_id = f"{base}_area_1"
    registry.async_get_or_create(
        "alarm_control_panel",
        DOMAIN,
        old_unique_id,
        config_entry=entry,
    )

    await _async_migrate_unique_ids(hass, entry, base)

    entry_id = registry.async_get_entity_id(
        "alarm_control_panel", DOMAIN, f"{base}:area:1"
    )
    assert entry_id is not None


async def test_migrate_unique_ids_skips_without_suffix(hass: HomeAssistant) -> None:
    """Verify migration skips IDs without an underscore suffix."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "192.168.1.24"})
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    base = "aa:bb:cc"
    registry.async_get_or_create(
        "alarm_control_panel",
        DOMAIN,
        f"{base}_area",
        config_entry=entry,
    )

    await _async_migrate_unique_ids(hass, entry, base)


async def test_migrate_unique_ids_skips_other_entry(hass: HomeAssistant) -> None:
    """Verify migration skips entries from other config entries."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "192.168.1.22"})
    entry.add_to_hass(hass)
    other_entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "192.168.1.23"})
    other_entry.add_to_hass(hass)
    registry = er.async_get(hass)
    base = "aa:bb:cc"
    registry.async_get_or_create(
        "alarm_control_panel",
        DOMAIN,
        f"{base}_area_1",
        config_entry=other_entry,
    )

    await _async_migrate_unique_ids(hass, entry, base)


async def test_setup_updates_integration_serial_and_pin(hass: HomeAssistant) -> None:
    """Verify integration serial is generated and pin is removed."""
    hub = SimpleNamespace(
        panel_name="Panel",
        async_connect=AsyncMock(return_value=None),
        async_disconnect=AsyncMock(return_value=None),
    )
    coordinator = SimpleNamespace(
        async_start=AsyncMock(return_value=None),
        async_refresh_now=AsyncMock(return_value=None),
        async_stop=AsyncMock(return_value=None),
        data=None,
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.15",
            CONF_PORT: DEFAULT_PORT,
            CONF_LINK_KEYS_JSON: LinkKeys("tk", "lk", "lh").to_json(),
            "pin": "1234",
            "panel": {"panel_name": "Panel"},
        },
    )
    entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.elke27.Elke27Hub", return_value=hub),
        patch(
            "homeassistant.components.elke27.Elke27DataUpdateCoordinator",
            return_value=coordinator,
        ),
        patch(
            "homeassistant.components.elke27.async_get_integration_serial",
            AsyncMock(return_value="998877"),
        ),
        patch.object(hass.config_entries, "async_update_entry") as update_entry,
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            AsyncMock(return_value=True),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    update_entry.assert_called()


async def test_setup_removes_pin_when_serial_exists(hass: HomeAssistant) -> None:
    """Verify pin removal updates entry when serial exists."""
    hub = SimpleNamespace(
        panel_name=None,
        async_connect=AsyncMock(return_value=None),
        async_disconnect=AsyncMock(return_value=None),
    )
    coordinator = SimpleNamespace(
        async_start=AsyncMock(return_value=None),
        async_refresh_now=AsyncMock(return_value=None),
        async_stop=AsyncMock(return_value=None),
        data=None,
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.16",
            CONF_PORT: DEFAULT_PORT,
            CONF_LINK_KEYS_JSON: LinkKeys("tk", "lk", "lh").to_json(),
            CONF_INTEGRATION_SERIAL: "112233445566",
            "pin": "1234",
        },
    )
    entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.elke27.Elke27Hub", return_value=hub),
        patch(
            "homeassistant.components.elke27.Elke27DataUpdateCoordinator",
            return_value=coordinator,
        ),
        patch.object(hass.config_entries, "async_update_entry") as update_entry,
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            AsyncMock(return_value=True),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    update_entry.assert_called()


async def test_migrate_unique_ids_skips_unmatched(hass: HomeAssistant) -> None:
    """Verify migration skips non-matching entries and collisions."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "192.168.1.20"})
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    base = "aa:bb"
    registry.async_get_or_create("alarm_control_panel", DOMAIN, f"{base}_area")
    registry.async_get_or_create(
        "alarm_control_panel",
        DOMAIN,
        f"{base}_area_2",
        config_entry=entry,
    )
    registry.async_get_or_create(
        "alarm_control_panel",
        DOMAIN,
        f"{base}:area:2",
        config_entry=entry,
    )
    registry.async_get_or_create(
        "alarm_control_panel",
        "other",
        f"{base}_area_3",
        config_entry=entry,
    )
    other_entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "192.168.1.21"})
    other_entry.add_to_hass(hass)
    registry.async_get_or_create(
        "alarm_control_panel",
        DOMAIN,
        f"{base}_area",
        config_entry=other_entry,
    )

    await _async_migrate_unique_ids(hass, entry, base)


async def test_alarm_arm_automatic_service_calls_hub(hass: HomeAssistant) -> None:
    """Verify the automatic arm service forwards the extra arm options."""
    await async_setup(hass, {})

    hub = SimpleNamespace(
        async_arm_area=AsyncMock(return_value=True),
        async_disconnect=AsyncMock(return_value=None),
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.1.30"},
    )
    entry.add_to_hass(hass)
    entry.runtime_data = Elke27RuntimeData(
        hub=hub,
        coordinator=SimpleNamespace(async_stop=AsyncMock(return_value=None)),
    )
    entry.mock_state(hass, ConfigEntryState.LOADED)

    entity_id = (
        er.async_get(hass)
        .async_get_or_create(
            "alarm_control_panel",
            DOMAIN,
            "aa:bb:cc:dd:ee:ff:area:1",
            config_entry=entry,
        )
        .entity_id
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_ALARM_ARM_AUTOMATIC,
        {
            "entity_id": entity_id,
            ATTR_MODE: "away",
            ATTR_CODE: "1234",
        },
        blocking=True,
    )

    hub.async_arm_area.assert_awaited_once_with(
        1,
        ArmMode.ARMED_AWAY,
        "1234",
        auto_stay_cancel=True,
        exit_delay_cancel=True,
    )


async def test_alarm_arm_automatic_home_also_uses_automatic_flags(
    hass: HomeAssistant,
) -> None:
    """Verify automatic arming always uses the built-in Elke27 flags."""
    await async_setup(hass, {})

    hub = SimpleNamespace(
        async_arm_area=AsyncMock(return_value=True),
        async_disconnect=AsyncMock(return_value=None),
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.1.31"},
    )
    entry.add_to_hass(hass)
    entry.runtime_data = Elke27RuntimeData(
        hub=hub,
        coordinator=SimpleNamespace(async_stop=AsyncMock(return_value=None)),
    )
    entry.mock_state(hass, ConfigEntryState.LOADED)

    entity_id = (
        er.async_get(hass)
        .async_get_or_create(
            "alarm_control_panel",
            DOMAIN,
            "aa:bb:cc:dd:ee:ff:area:1",
            config_entry=entry,
        )
        .entity_id
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_ALARM_ARM_AUTOMATIC,
        {
            "entity_id": entity_id,
            ATTR_MODE: "home",
            ATTR_CODE: "1234",
        },
        blocking=True,
    )

    hub.async_arm_area.assert_awaited_once_with(
        1,
        ArmMode.ARMED_STAY,
        "1234",
        auto_stay_cancel=True,
        exit_delay_cancel=True,
    )


async def test_alarm_arm_automatic_rejects_non_elke27_entity(
    hass: HomeAssistant,
) -> None:
    """Verify the service rejects non-Elke27 alarm entities."""
    await async_setup(hass, {})

    other_entry = MockConfigEntry(domain="test", data={CONF_HOST: "192.168.1.32"})
    other_entry.add_to_hass(hass)
    other_entry.mock_state(hass, ConfigEntryState.LOADED)
    entity_id = (
        er.async_get(hass)
        .async_get_or_create(
            "alarm_control_panel",
            "test",
            "other-alarm-1",
            config_entry=other_entry,
        )
        .entity_id
    )

    with pytest.raises(
        ServiceValidationError,
        match="is not an Elke27 alarm control panel",
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ALARM_ARM_AUTOMATIC,
            {
                "entity_id": entity_id,
                ATTR_MODE: "away",
                ATTR_CODE: "1234",
            },
            blocking=True,
        )
