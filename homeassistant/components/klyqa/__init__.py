"""Support for Klyqa smart devices."""
from __future__ import annotations

from datetime import timedelta
from typing import Any, Callable

from klyqa_ctl import klyqa_ctl as api

from homeassistant.components.light import ENTITY_ID_FORMAT as LIGHT_ENTITY_ID_FORMAT
from homeassistant.components.vacuum import ENTITY_ID_FORMAT as VACUUM_ENTITY_ID_FORMAT
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_RESTORED,
    CONF_PASSWORD,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as ent_reg
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import slugify

from .const import (
    DOMAIN,
    EVENT_KLYQA_NEW_LIGHT,
    EVENT_KLYQA_NEW_LIGHT_GROUP,
    EVENT_KLYQA_NEW_VC,
)

PLATFORMS: list[Platform] = [Platform.LIGHT, Platform.VACUUM]
SCAN_INTERVAL: timedelta = timedelta(seconds=120)


class HAKlyqaAccount(api.Klyqa_account):  # type: ignore[misc]
    """HAKlyqaAccount."""

    hass: HomeAssistant

    polling: bool

    def __init__(
        self,
        hass: HomeAssistant,
        data_communicator: api.Data_communicator,
        username: str = "",
        password: str = "",
        polling: bool = True,
        entry: ConfigEntry | None = None,
    ) -> None:
        """HAKlyqaAccount."""
        super().__init__(data_communicator, username, password)
        self.hass = hass
        self.polling = polling
        self.entry: ConfigEntry = entry

    async def login(self, print_onboarded_devices=False) -> bool:
        """Login."""
        ret: bool = await super().login(print_onboarded_devices=False)
        if ret:
            await api.async_json_cache(
                {CONF_USERNAME: self.username, CONF_PASSWORD: self.password},
                "last.klyqa_integration_data.cache.json",
            )
        return ret

    async def update_account(self, device_type: str) -> None:
        """Update_account."""

        await self.request_account_settings()
        # await self.request_account_settings_eco()

        await self.process_account_settings(device_type)

    async def process_account_settings(self, device_type: str) -> None:
        """Process_account_settings."""
        if self.acc_settings is None:
            return None

        def sync_account_devices_with_ha_entities(device_type: str) -> None:
            if self.acc_settings is None:
                return None
            entity_registry = ent_reg.async_get(self.hass)

            for device in self.acc_settings["devices"]:
                # look if any onboarded device is not in the entity registry already
                u_id = api.format_uid(device["localDeviceId"])

                platform: str = ""
                entity_id: str = ""
                event: str = ""
                if (
                    device_type == api.DeviceType.lighting.name
                    and device["productId"].find(".lighting") > -1
                ):
                    platform = Platform.LIGHT
                    entity_id = LIGHT_ENTITY_ID_FORMAT.format(u_id)
                    event = EVENT_KLYQA_NEW_LIGHT
                elif (
                    device_type == api.DeviceType.cleaner.name
                    and device["productId"].find(".cleaning") > -1
                ):
                    platform = Platform.VACUUM
                    entity_id = VACUUM_ENTITY_ID_FORMAT.format(u_id)
                    event = EVENT_KLYQA_NEW_VC
                else:
                    continue
                registered_entity_id = entity_registry.async_get_entity_id(
                    platform, DOMAIN, u_id
                )

                existing = (
                    self.hass.states.get(registered_entity_id)
                    if registered_entity_id
                    else self.hass.states.get(entity_id)
                )
                if (
                    not registered_entity_id
                    or not existing
                    or ATTR_RESTORED in existing.attributes
                ):
                    self.hass.bus.fire(event, device)

            if device_type == api.DeviceType.lighting.name:
                for group in self.acc_settings["deviceGroups"]:
                    u_id = api.format_uid(group["id"])
                    entity_id = LIGHT_ENTITY_ID_FORMAT.format(slugify(group["id"]))

                    registered_entity_id = entity_registry.async_get_entity_id(
                        Platform.LIGHT, DOMAIN, slugify(group["id"])  # u_id
                    )
                    # existing = self.hass.states.get(entity_id)
                    existing = (
                        self.hass.states.get(registered_entity_id)
                        if registered_entity_id
                        else self.hass.states.get(entity_id)
                    )

                    if (
                        not registered_entity_id
                        or not existing
                        or ATTR_RESTORED in existing.attributes
                    ):
                        """found klyqa device not in the light entities"""
                        if (
                            len(group["devices"]) > 0
                            and "productId" in group["devices"][0]
                            and group["devices"][0]["productId"].startswith(
                                "@klyqa.lighting"
                            )
                        ):
                            self.hass.bus.fire(EVENT_KLYQA_NEW_LIGHT_GROUP, group)

        klyqa_new_light_registered: list[str]
        if device_type == api.DeviceType.lighting.name:
            klyqa_new_light_registered = [
                key
                for key, _ in self.hass.bus.async_listeners().items()
                if key == EVENT_KLYQA_NEW_LIGHT or key == EVENT_KLYQA_NEW_LIGHT_GROUP
            ]
            if len(klyqa_new_light_registered) == 2:
                sync_account_devices_with_ha_entities(device_type)

        elif device_type == api.DeviceType.cleaner.name:
            klyqa_new_light_registered = [
                key
                for key, _ in self.hass.bus.async_listeners().items()
                if key == EVENT_KLYQA_NEW_VC
            ]
            if len(klyqa_new_light_registered) == 1:
                sync_account_devices_with_ha_entities(device_type)

        return True


class KlyqaData:
    """KlyqaData class."""

    def __init__(
        self, data_communicator: api.Data_communicator, polling: bool = True
    ) -> None:
        """Initialize the system."""
        self.data_communicator: api.Data_communicator = data_communicator
        self.polling: bool = polling
        self.entity_ids: set[str | None] = set()
        self.entries: dict[str, HAKlyqaAccount] = {}
        self.remove_listeners: list[Callable] = []
        self.entities_area_update: dict[str, set[str]] = {}


async def async_setup(hass: HomeAssistant, yaml_config: ConfigType) -> bool:
    """Set up the klyqa component."""
    if DOMAIN in hass.data:
        return True
    hass.data[DOMAIN] = KlyqaData(api.Data_communicator())
    klyqa: KlyqaData = hass.data[DOMAIN]

    await klyqa.data_communicator.bind_ports()

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up or change Klyqa integration from a config entry."""

    username = str(entry.data.get(CONF_USERNAME))
    password = str(entry.data.get(CONF_PASSWORD))

    klyqa_data: KlyqaData = hass.data[DOMAIN]

    account: HAKlyqaAccount | None = None

    if entry.entry_id in klyqa_data.entries:
        account = klyqa_data.entries[entry.entry_id]
        if account:
            await hass.async_add_executor_job(account.shutdown)

            account.username = username
            account.password = password
            account.data_communicator = klyqa_data.data_communicator

    else:
        account = HAKlyqaAccount(
            hass, klyqa_data.data_communicator, username, password, entry=entry
        )
        if not hasattr(klyqa_data, "entries"):
            klyqa_data.entries = {}
        klyqa_data.entries[entry.entry_id] = account

    if not account or not await account.login():
        return False

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    async def shutdown_klyqa_account(*_: Any) -> None:
        if account:
            account.shutdown()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, shutdown_klyqa_account)

    # For previous config entries where unique_id is None
    if entry.unique_id is None:
        hass.config_entries.async_update_entry(
            entry, unique_id=entry.data[CONF_USERNAME]
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    klyqa_data: KlyqaData = hass.data[DOMAIN]

    unload_ok: bool = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    while klyqa_data.remove_listeners:
        listener: Callable = klyqa_data.remove_listeners.pop(-1)
        if callable(listener):
            listener()

    if DOMAIN in hass.data:
        if entry.entry_id in klyqa_data.entries:
            if klyqa_data.entries[entry.entry_id]:
                account: api.Klyqa_account = klyqa_data.entries[entry.entry_id]
                await hass.async_add_executor_job(account.shutdown)
            klyqa_data.entries.pop(entry.entry_id)

    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle an options update."""
    await hass.config_entries.async_reload(entry.entry_id)
