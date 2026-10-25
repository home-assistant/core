"""Common helper functions."""

import asyncio
from collections.abc import Awaitable, Callable, Coroutine
import itertools
from typing import Any
from unittest.mock import MagicMock, create_autospec

from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.visonic.const import (
    CONF_ARM_CODE_AUTO,
    CONF_ARM_HOME_ENABLED,
    CONF_DOWNLOAD_CODE,
    CONF_ENABLE_REMOTE_ARM,
    CONF_ENABLE_REMOTE_DISARM,
    CONF_EPROM_ATTRIBUTES,
    CONF_INSTANT_ARM_AWAY,
    CONF_INSTANT_ARM_HOME,
    CONF_PANEL_NUMBER,
    CONF_PANEL_SERIAL,
    CONF_RETRY_CONNECTION_COUNT,
    CONF_RETRY_CONNECTION_DELAY,
    CONF_USER_CODE_SLOT,
    DOMAIN,
)
from homeassistant.components.visonic.visonic_data_types import VisonicConfigEntry
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_CODE,
    CONF_EMAIL,
    CONF_EXTERNAL_URL,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PATH,
    CONF_PORT,
    CONF_TYPE,
)
from homeassistant.core import HomeAssistant

type SetupIntegration = Callable[..., Awaitable[tuple[bool, VisonicConfigEntry]]]

_counter = itertools.count()


def create_mock_config_entry(
    data: dict[str, Any] | None = None,
    options: dict[str, Any] | None = None,
    delete_data: list[str] | None = None,
) -> MockConfigEntry:
    """Create a real config entry using the panel test defaults."""
    example = create_config_entry_example(
        data=data, options=options, delete_data=delete_data
    )
    return MockConfigEntry(
        domain=DOMAIN,
        data=dict(example.data),
        options=dict(example.options),
        title=example.title,
    )


def create_config_entry_empty(
    data: dict | None = None,
    options: dict | None = None,
) -> ConfigEntry:
    """Create an empty config entry, adding the provided parameters."""
    entry: ConfigEntry = create_autospec(ConfigEntry, instance=True)
    entry.async_on_unload = MagicMock(side_effect=lambda func: func)

    # entry.add_update_listener = MagicMock()

    def _fake_bg_task(
        hass: HomeAssistant,
        coro: Coroutine[Any, Any, None],
        name: str,
        eager_start: bool = True,
    ) -> asyncio.Task[None]:
        return hass.async_create_background_task(coro, name, eager_start=eager_start)

    entry.async_create_background_task = MagicMock(side_effect=_fake_bg_task)

    def _fake_task(
        hass: HomeAssistant, coro: Coroutine[Any, Any, None], name: str
    ) -> asyncio.Task[None]:
        return hass.async_create_task(coro, name)

    entry.async_create_task = MagicMock(side_effect=_fake_task)
    entry.pref_disable_polling = False
    entry.pref_disable_new_entities = False
    entry.domain = DOMAIN
    uid = next(_counter)
    entry.title = f"Test panel entry {uid}"
    entry.version = 7
    # Make the entry_id unique
    entry.entry_id = f"entry_{uid}"
    entry.data = {}
    entry.options = {}
    if data is not None:
        entry.data.update(data)
    if options is not None:
        entry.options.update(options)
    entry.runtime_data = None
    return entry


def create_config_entry_example(
    data: dict | None = None,
    delete_data: list | None = None,
    options: dict | None = None,
    delete_options: list | None = None,
) -> ConfigEntry:
    """Create a typical (example, working) config entry, with the possibility of adding/changing/deleting data and options items."""
    entry = create_config_entry_empty()

    entry.data = {
        CONF_TYPE: "ethernet",
        CONF_HOST: "192.168.0.10",
        CONF_PORT: 10000,
        CONF_PATH: "COM1",
        CONF_PANEL_NUMBER: 1,
        CONF_EXTERNAL_URL: "",
        CONF_EPROM_ATTRIBUTES: True,
        CONF_USER_CODE_SLOT: 1,
        CONF_EMAIL: "",
        CONF_PASSWORD: "",
        CONF_CODE: "",
        CONF_PANEL_SERIAL: "",
    }

    entry.options = {
        CONF_ARM_HOME_ENABLED: True,
        CONF_RETRY_CONNECTION_DELAY: 10,
        CONF_ENABLE_REMOTE_ARM: False,
        CONF_ENABLE_REMOTE_DISARM: False,
        CONF_INSTANT_ARM_HOME: True,
        CONF_INSTANT_ARM_AWAY: False,
        CONF_RETRY_CONNECTION_COUNT: 0,
        CONF_DOWNLOAD_CODE: "",
        CONF_ARM_CODE_AUTO: False,
    }

    if delete_data is not None:
        for d in delete_data:
            entry.data.pop(d, None)
    if delete_options is not None:
        for d in delete_options:
            entry.options.pop(d, None)
    if data is not None:
        entry.data.update(data)
    if options is not None:
        entry.options.update(options)
    return entry
