"""The yalexs_ble integration models."""

from dataclasses import dataclass

from yalexs_ble import LockActivity, PushLock

from homeassistant.core import Context

from .store import CredentialNames


@dataclass
class YaleXSBLEData:
    """Data for the yale xs ble integration."""

    title: str
    lock: PushLock
    always_connected: bool
    credential_names: CredentialNames
    master_code_name: str | None = None
    last_activity: LockActivity | None = None
    last_activity_context: Context | None = None
