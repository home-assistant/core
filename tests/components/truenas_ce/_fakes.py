"""Shared test doubles for platform-module unit tests.

These build a lightweight stand-in for ``TrueNASCoordinator`` (a real
``DataUpdateCoordinator`` subclass) so entity classes can be constructed and
exercised without a running ``HomeAssistant`` core instance, mirroring the
``BaseCoordinatorEntity.__init__`` contract (it only stores ``coordinator``
and ``coordinator_context``, no hass access at construction time).
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from homeassistant.const import CONF_HOST, CONF_NAME

DEFAULT_SYSTEM_INFO: dict[str, Any] = {
    "hostname": "truenas.local",
    "system_product": "TrueNAS Mini",
    "system_manufacturer": "iXsystems",
    "version": "TrueNAS-25.10.4",
}


def make_config_entry(
    *,
    name: str = "TrueNAS",
    host: str = "truenas.local",
    entry_id: str = "TrueNAS",
    data: dict[str, Any] | None = None,
    options: dict[str, Any] | None = None,
) -> SimpleNamespace:
    """Build a minimal stand-in for a ConfigEntry.

    ``entry_id`` defaults to the same string as the default ``name`` so
    identity-based unique_ids/device identifiers (see
    ``entity.resolve_entry_identity``) keep matching pre-existing test
    expectations that were written against the old name-based format;
    pass distinct ``entry_id``/``data={CONF_SYSTEM_ID: ...}`` values to
    exercise the identity-vs-display-name distinction explicitly.
    """
    entry_data = {CONF_NAME: name, CONF_HOST: host, **(data or {})}
    return SimpleNamespace(
        entry_id=entry_id,
        data=entry_data,
        options=options or {},
        async_get_entry=MagicMock(return_value=None),
    )


def make_coordinator(
    *,
    data: dict[str, Any] | None = None,
    config_entry: SimpleNamespace | None = None,
    api_error: str = "",
    api_scheme: str = "ws",
    host: str = "truenas.local",
) -> SimpleNamespace:
    """Build a minimal stand-in for TrueNASCoordinator.

    Only the attributes actually touched by entity.py/sensor.py are provided;
    add more as new tests need them.
    """
    ds = {"system_info": dict(DEFAULT_SYSTEM_INFO), **(data or {})}
    entry = config_entry or make_config_entry(host=host)
    api = SimpleNamespace(
        query=AsyncMock(return_value=None),
        error=api_error,
        scheme=api_scheme,
    )
    return SimpleNamespace(
        data=ds,
        ds=ds,
        config_entry=entry,
        api=api,
        host=host,
        hass=SimpleNamespace(
            config_entries=SimpleNamespace(
                async_get_entry=MagicMock(return_value=None),
                async_update_entry=MagicMock(),
            )
        ),
        last_update_success=True,
        system_device_id="test-system-device-id",
        async_refresh=AsyncMock(),
        async_request_refresh=AsyncMock(),
        supports_update_run=MagicMock(return_value=True),
    )
