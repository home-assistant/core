"""The Mammotion integration."""

from typing import Any

from aiohttp import ClientError
from pymammotion.aliyun.exceptions import CloudSetupError
from pymammotion.aliyun.model.dev_by_account_response import Device
from pymammotion.client import MammotionClient
from pymammotion.homeassistant import HomeAssistantMowerApi
from pymammotion.http.model.http import UnauthorizedExceptionError
from pymammotion.transport.base import (
    AuthError,
    LoginFailedError,
    TransportType,
    is_transient_network_error,
)
from Tea.exceptions import UnretryableException

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import (
    CONF_PASSWORD,
    EVENT_HOMEASSISTANT_FINAL_WRITE,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
    __version__ as HA_VERSION,
)
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import AnyDeviceEntry

from .config import MammotionConfigStore
from .const import (
    CONF_ACCOUNTNAME,
    CONF_AEP_DATA,
    CONF_MAMMOTION_DEVICE_RECORDS,
    CONF_MAMMOTION_MQTT,
    DEVICE_SUPPORT,
    DOMAIN,
    LOGGER,
)
from .coordinator import MammotionMowerUpdateCoordinator
from .models import MammotionDevices, MammotionMowerData

PLATFORMS: list[Platform] = [Platform.LAWN_MOWER]

type MammotionConfigEntry = ConfigEntry[MammotionDevices]


async def async_setup_entry(hass: HomeAssistant, entry: MammotionConfigEntry) -> None:
    """Set up Mammotion Luba from a config entry."""
    session = async_get_clientsession(hass)
    api = HomeAssistantMowerApi(ha_version=HA_VERSION, session=session)
    mammotion = api.mammotion

    async def shutdown_mammotion(_: Event | None = None) -> None:
        await mammotion.stop()

    # Registered before login so a failed setup does not leave the client's
    # MQTT session running into the retry, which reuses the same client_id.
    entry.async_on_unload(shutdown_mammotion)
    # Not async_listen_once: unloading after the event fired would remove it twice.
    entry.async_on_unload(
        hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, shutdown_mammotion)
    )

    account = entry.data[CONF_ACCOUNTNAME]
    password = entry.data[CONF_PASSWORD]

    store = MammotionConfigStore(hass, entry.entry_id)
    await store.async_load_mower_data()

    async def credentials_updated() -> None:
        """Persist credentials the library rotated behind our back."""
        store_cloud_credentials(hass, entry, mammotion)

    async def unrecoverable_auth_error(
        account_id: str, transport_type: TransportType, err: Exception
    ) -> None:
        """Surface a dead cloud session as a single reauth prompt."""
        LOGGER.error(
            "Mammotion cloud authentication failed for %s on %s: %s",
            account_id,
            transport_type.value,
            err,
        )
        entry.async_start_reauth(hass)

    # Wired before login so a rotation during it is not lost.
    mammotion.on_credentials_updated = credentials_updated
    mammotion.on_unrecoverable_auth_error = unrecoverable_auth_error

    try:
        if cached := _load_cached_credentials(entry):
            await mammotion.restore_credentials(account, password, cached, session)
        else:
            await mammotion.login_and_initiate_cloud(account, password, session)
    except (ClientError, TimeoutError, ConnectionError, CloudSetupError) as err:
        raise ConfigEntryNotReady(err) from err
    except (AuthError, UnauthorizedExceptionError) as err:
        # A transport-scoped refusal raises the same errors while the login holds.
        if isinstance(err, LoginFailedError) or mammotion.reauth_required is not None:
            raise ConfigEntryAuthFailed(err) from err
        raise ConfigEntryNotReady(err) from err
    except UnretryableException as err:
        # Tea raises this once its retries of a network error are spent.
        if is_transient_network_error(err):
            raise ConfigEntryNotReady(err) from err
        raise ConfigEntryError(err) from err

    store_cloud_credentials(hass, entry, mammotion)

    device_list: list[Device] = [
        device
        for device in (*mammotion.aliyun_device_list, *mammotion.mammotion_device_list)
        if device.device_name.startswith(DEVICE_SUPPORT)
    ]

    mowers: list[MammotionMowerData] = []
    for device in device_list:
        update_coordinator = MammotionMowerUpdateCoordinator(
            hass, entry, device, api, store
        )
        update_coordinator.restore_data()
        await update_coordinator.async_config_entry_first_refresh()
        mowers.append(
            MammotionMowerData(
                name=device.device_name,
                api=api,
                coordinator=update_coordinator,
                device=device,
            )
        )

    entry.runtime_data = MammotionDevices(mowers)

    entry.async_on_unload(
        hass.bus.async_listen(
            EVENT_HOMEASSISTANT_FINAL_WRITE, store.async_flush_mower_data
        )
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


def store_cloud_credentials(
    hass: HomeAssistant,
    config_entry: MammotionConfigEntry,
    mammotion: MammotionClient,
) -> None:
    """Store cloud credentials in config entry."""
    if cache := mammotion.to_cache():
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


async def async_unload_entry(hass: HomeAssistant, entry: MammotionConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)

    if not (mowers := entry.runtime_data.mowers):
        return

    store_cloud_credentials(hass, entry, mowers[0].api.mammotion)
    for mower in mowers:
        await mower.api.mammotion.remove_device(mower.name)
    await mowers[0].coordinator.store.async_flush_mower_data()


async def async_remove_entry(hass: HomeAssistant, entry: MammotionConfigEntry) -> None:
    """Remove a config entry."""
    store = MammotionConfigStore(hass, entry.entry_id)
    await store.async_remove()


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    config_entry: MammotionConfigEntry,
    device_entry: AnyDeviceEntry,
) -> bool:
    """Allow removing a device only once its mower is gone from the account."""
    # The mower list is unknown while unloaded; a mower still on the account
    # gets its device back on the next setup.
    if config_entry.state is not ConfigEntryState.LOADED:
        return True
    mower_names = {mower.name for mower in config_entry.runtime_data.mowers}
    return not any(
        domain == DOMAIN and name in mower_names
        for domain, name in device_entry.identifiers
    )
