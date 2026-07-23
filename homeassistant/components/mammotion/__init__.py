"""The Mammotion integration."""

import contextlib
from typing import Any

from aiohttp import ClientConnectorError
from pymammotion.aliyun.model.dev_by_account_response import Device
from pymammotion.client import MammotionClient
from pymammotion.homeassistant import HomeAssistantMowerApi
from Tea.exceptions import UnretryableException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntry

from .config import MammotionConfigStore
from .const import (
    CONF_ACCOUNTNAME,
    CONF_AEP_DATA,
    CONF_MAMMOTION_DEVICE_RECORDS,
    CONF_MAMMOTION_MQTT,
    DEVICE_SUPPORT,
    DOMAIN,
    EXPIRED_CREDENTIAL_EXCEPTIONS,
)
from .coordinator import MammotionMowerUpdateCoordinator
from .models import MammotionDevices, MammotionMowerData

PLATFORMS: list[Platform] = [Platform.LAWN_MOWER]

type MammotionConfigEntry = ConfigEntry[MammotionDevices]


async def async_setup_entry(hass: HomeAssistant, entry: MammotionConfigEntry) -> bool:
    """Set up Mammotion Luba from a config entry."""

    api = HomeAssistantMowerApi(async_get_clientsession(hass))
    mammotion = api.mammotion
    account = entry.data.get(CONF_ACCOUNTNAME)
    password = entry.data.get(CONF_PASSWORD)

    mammotion_mowers: list[MammotionMowerData] = []
    mammotion_devices: MammotionDevices = MammotionDevices([])
    store = MammotionConfigStore(hass)

    if account and password:
        session = async_get_clientsession(hass)
        cached = _load_cached_credentials(entry)
        try:
            if cached:
                try:
                    await mammotion.restore_credentials(
                        account, password, cached, session
                    )
                except EXPIRED_CREDENTIAL_EXCEPTIONS:
                    await mammotion.login_and_initiate_cloud(account, password, session)
            else:
                await mammotion.login_and_initiate_cloud(account, password, session)
        except ClientConnectorError as err:
            raise ConfigEntryNotReady(err) from err
        except UnretryableException as err:
            raise ConfigEntryError(err) from err

        store_cloud_credentials(hass, entry, mammotion)

        device_list: list[Device] = [
            device
            for device in (
                *mammotion.aliyun_device_list,
                *mammotion.mammotion_device_list,
            )
            if device.device_name.startswith(DEVICE_SUPPORT)
        ]

        for device in device_list:
            update_coordinator = MammotionMowerUpdateCoordinator(
                hass, entry, device, api, store
            )

            await update_coordinator.async_restore_data()
            await update_coordinator.async_config_entry_first_refresh()

            mammotion_mowers.append(
                MammotionMowerData(
                    name=device.device_name,
                    api=api,
                    coordinator=update_coordinator,
                    device=device,
                )
            )

    mammotion_devices.mowers = mammotion_mowers
    entry.runtime_data = mammotion_devices

    async def shutdown_mammotion(_: Event | None = None) -> None:
        await mammotion.stop()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, shutdown_mammotion)
    )
    entry.async_on_unload(shutdown_mammotion)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


def store_cloud_credentials(
    hass: HomeAssistant,
    config_entry: MammotionConfigEntry,
    mammotion: MammotionClient,
) -> None:
    """Store cloud credentials in config entry."""
    cache = mammotion.to_cache()
    if not cache:
        return
    hass.config_entries.async_update_entry(
        config_entry, data={**config_entry.data, **cache}
    )


def _load_cached_credentials(entry: MammotionConfigEntry) -> dict[str, Any]:
    """Return the config entry's cached credential data, keyed as the library expects."""
    has_aliyun = bool(entry.data.get(CONF_AEP_DATA))
    has_mammotion = bool(entry.data.get(CONF_MAMMOTION_MQTT)) and bool(
        entry.data.get(CONF_MAMMOTION_DEVICE_RECORDS)
    )
    return dict(entry.data) if (has_aliyun or has_mammotion) else {}


async def async_unload_entry(hass: HomeAssistant, entry: MammotionConfigEntry) -> bool:
    """Unload a config entry."""

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        for mower in entry.runtime_data.mowers:
            mower.coordinator.store_cloud_credentials()
            with contextlib.suppress(TimeoutError):
                await mower.api.mammotion.remove_device(mower.name)
    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: MammotionConfigEntry) -> None:
    """Remove a config entry."""
    store = MammotionConfigStore(hass)
    await store.async_remove()


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: MammotionConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Remove a config entry from a device."""
    mower_names = (
        next(
            identifier[1]
            for identifier in device_entry.identifiers
            if identifier[0] == DOMAIN
        ),
    )
    mower = next(
        (
            mower
            for mower in config_entry.runtime_data.mowers
            if mower.name in mower_names
        ),
        None,
    )

    return not bool(mower)
