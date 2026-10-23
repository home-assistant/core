"""Velbus services tests."""

import errno
import os
from unittest.mock import AsyncMock, MagicMock, patch

import probatio
import pytest

from homeassistant.components.velbus.const import (
    CONF_CONFIG_ENTRY,
    CONF_MEMO_TEXT,
    DOMAIN,
    SERVICE_CLEAR_CACHE,
    SERVICE_SCAN,
    SERVICE_SET_MEMO_TEXT,
    SERVICE_SYNC,
)
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.storage import STORAGE_DIR

from . import init_integration

from tests.common import MockConfigEntry


async def test_global_services_with_config_entry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test services directed at the bus with a config_entry."""
    await init_integration(hass, config_entry)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SCAN,
        {CONF_CONFIG_ENTRY: config_entry.entry_id},
        blocking=True,
    )
    config_entry.runtime_data.controller.scan.assert_called_once_with()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SYNC,
        {CONF_CONFIG_ENTRY: config_entry.entry_id},
        blocking=True,
    )
    config_entry.runtime_data.controller.sync_clock.assert_called_once_with()

    # Test invalid interface
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SCAN,
            {CONF_CONFIG_ENTRY: "nonexistent"},
            blocking=True,
        )

    # Test missing interface
    with pytest.raises(probatio.error.MultipleInvalid):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SCAN,
            {},
            blocking=True,
        )

    # Test scan with OSError
    config_entry.runtime_data.controller.scan.side_effect = OSError("Boom")
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SCAN,
            {CONF_CONFIG_ENTRY: config_entry.entry_id},
            blocking=True,
        )

    # Test sync_clock with OSError
    config_entry.runtime_data.controller.sync_clock.side_effect = OSError("Boom")
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SYNC,
            {CONF_CONFIG_ENTRY: config_entry.entry_id},
            blocking=True,
        )


async def test_set_memo_text(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    controller: AsyncMock,
) -> None:
    """Test the set_memo_text service."""
    await init_integration(hass, config_entry)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_MEMO_TEXT,
        {
            CONF_CONFIG_ENTRY: config_entry.entry_id,
            CONF_MEMO_TEXT: "Test",
            CONF_ADDRESS: 1,
        },
        blocking=True,
    )
    config_entry.runtime_data.controller.get_module(
        1
    ).set_memo_text.assert_called_once_with("Test")

    # Test with OSError
    controller.return_value.get_module.return_value.set_memo_text.side_effect = OSError(
        "Boom"
    )
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_MEMO_TEXT,
            {
                CONF_CONFIG_ENTRY: config_entry.entry_id,
                CONF_MEMO_TEXT: "Test",
                CONF_ADDRESS: 2,
            },
            blocking=True,
        )
    controller.return_value.get_module.return_value.set_memo_text.side_effect = None

    # Test with unfound module
    controller.return_value.get_module.return_value = None
    with pytest.raises(ServiceValidationError, match="Module with address 2 not found"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_MEMO_TEXT,
            {
                CONF_CONFIG_ENTRY: config_entry.entry_id,
                CONF_MEMO_TEXT: "Test",
                CONF_ADDRESS: 2,
            },
            blocking=True,
        )


async def test_clear_cache(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test the clear_cache service."""
    await init_integration(hass, config_entry)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_CLEAR_CACHE,
        {CONF_CONFIG_ENTRY: config_entry.entry_id},
        blocking=True,
    )
    config_entry.runtime_data.controller.scan.assert_called_once_with()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_CLEAR_CACHE,
        {CONF_CONFIG_ENTRY: config_entry.entry_id, CONF_ADDRESS: 1},
        blocking=True,
    )
    assert config_entry.runtime_data.controller.scan.call_count == 2


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(errno.EACCES, id="permission_denied"),
        pytest.param(errno.EIO, id="io_error"),
    ],
)
@pytest.mark.parametrize(
    ("service_data", "patch_target", "cache_name"),
    [
        pytest.param(
            {CONF_ADDRESS: 2}, ("os.path.exists", "os.unlink"), "2.p", id="file"
        ),
        pytest.param({}, ("os.path.isdir", "shutil.rmtree"), "", id="dir"),
    ],
)
async def test_clear_cache_error(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    error: int,
    service_data: dict[str, int],
    patch_target: tuple[str, str],
    cache_name: str,
) -> None:
    """Test clear_cache raises a translated error when deleting the cache fails."""
    await init_integration(hass, config_entry)

    with (
        patch(patch_target[0], return_value=True),
        patch(patch_target[1], side_effect=OSError(error, os.strerror(error))),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_CLEAR_CACHE,
            {CONF_CONFIG_ENTRY: config_entry.entry_id, **service_data},
            blocking=True,
        )

    assert exc_info.value.translation_key == "clear_cache_failed"
    assert exc_info.value.translation_placeholders == {
        "path": hass.config.path(
            STORAGE_DIR, f"velbuscache-{config_entry.entry_id}/{cache_name}"
        )
    }
    config_entry.runtime_data.controller.scan.assert_not_called()


@pytest.mark.parametrize(
    ("service_data", "patch_target", "patch_func"),
    [
        pytest.param(
            {CONF_ADDRESS: 1},
            ("os.path.exists", "os.unlink"),
            (True, MagicMock()),
            id="file_exists_unlink",
        ),
        pytest.param(
            {},
            ("os.path.isdir", "shutil.rmtree"),
            (True, MagicMock()),
            id="dir_exists_rmtree",
        ),
    ],
)
async def test_clear_cache_path_exists(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    service_data: dict,
    patch_target: tuple[str, str],
    patch_func: tuple,
) -> None:
    """Test clear_cache when the cache path actually exists."""
    await init_integration(hass, config_entry)

    exists_mock = MagicMock(return_value=patch_func[0])
    op_mock = MagicMock()
    with (
        patch(patch_target[0], exists_mock),
        patch(patch_target[1], op_mock),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_CLEAR_CACHE,
            {CONF_CONFIG_ENTRY: config_entry.entry_id, **service_data},
            blocking=True,
        )
        exists_mock.assert_called_once()
        op_mock.assert_called_once()
    config_entry.runtime_data.controller.scan.assert_called_once_with()
