"""Provide persistent configuration for the hassio integration."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Required, Self, TypedDict

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import UNDEFINED, UndefinedType

from .const import DOMAIN

STORE_DELAY_SAVE = 30
STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1
STORAGE_VERSION_MINOR = 1


class HassioConfig:
    """Handle update config."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize update config."""
        self.data = HassioConfigData(
            hassio_user=None,
            update_config=HassioUpdateConfig(),
        )
        self._hass = hass
        self._store = HassioConfigStore(hass, self)

    async def load(self) -> None:
        """Load config."""
        if not (store_data := await self._store.load()):
            return
        self.data = HassioConfigData.from_dict(store_data)

    @callback
    def update(
        self,
        *,
        hassio_user: str | UndefinedType = UNDEFINED,
        update_config: HassioUpdateParametersDict | UndefinedType = UNDEFINED,
    ) -> None:
        """Update config."""
        if hassio_user is not UNDEFINED:
            self.data.hassio_user = hassio_user
        if update_config is not UNDEFINED:
            self.data.update_config = replace(self.data.update_config, **update_config)

        self._store.save()


@dataclass(kw_only=True)
class HassioConfigData:
    """Represent loaded update config data."""

    hassio_user: str | None
    update_config: HassioUpdateConfig

    @classmethod
    def from_dict(cls, data: StoredHassioConfig) -> Self:
        """Initialize update config data from a dict."""
        if update_data := data.get("update_config"):
            update_config = HassioUpdateConfig(
                add_on_backup_before_update=update_data["add_on_backup_before_update"],
                add_on_backup_retain_copies=update_data["add_on_backup_retain_copies"],
                core_backup_before_update=update_data["core_backup_before_update"],
            )
        else:
            update_config = HassioUpdateConfig()
        return cls(
            hassio_user=data["hassio_user"],
            update_config=update_config,
        )

    def to_dict(self) -> StoredHassioConfig:
        """Convert update config data to a dict."""
        return StoredHassioConfig(
            hassio_user=self.hassio_user,
            update_config=self.update_config.to_dict(),
        )


@dataclass(kw_only=True)
class HassioUpdateConfig:
    """Represent the backup retention configuration."""

    add_on_backup_before_update: bool = False
    add_on_backup_retain_copies: int = 1
    core_backup_before_update: bool = False

    def to_dict(self) -> StoredHassioUpdateConfig:
        """Convert backup retention configuration to a dict."""
        return StoredHassioUpdateConfig(
            add_on_backup_before_update=self.add_on_backup_before_update,
            add_on_backup_retain_copies=self.add_on_backup_retain_copies,
            core_backup_before_update=self.core_backup_before_update,
        )


class HassioUpdateParametersDict(TypedDict, total=False):
    """Represent the parameters for update."""

    add_on_backup_before_update: bool
    add_on_backup_retain_copies: int
    core_backup_before_update: bool


class HassioConfigStore:
    """Store hassio config."""

    def __init__(self, hass: HomeAssistant, config: HassioConfig) -> None:
        """Initialize the hassio config store."""
        self._hass = hass
        self._config = config
        self._store: Store[StoredHassioConfig] = Store(
            hass, STORAGE_VERSION, STORAGE_KEY, minor_version=STORAGE_VERSION_MINOR
        )

    async def load(self) -> StoredHassioConfig | None:
        """Load the store."""
        return await self._store.async_load()

    @callback
    def save(self) -> None:
        """Save config."""
        self._store.async_delay_save(self._data_to_save, STORE_DELAY_SAVE)

    @callback
    def _data_to_save(self) -> StoredHassioConfig:
        """Return data to save."""
        return self._config.data.to_dict()


class StoredHassioConfig(TypedDict, total=False):
    """Represent the stored hassio config."""

    hassio_user: Required[str | None]
    update_config: StoredHassioUpdateConfig


class StoredHassioUpdateConfig(TypedDict):
    """Represent the stored update config."""

    add_on_backup_before_update: bool
    add_on_backup_retain_copies: int
    core_backup_before_update: bool
