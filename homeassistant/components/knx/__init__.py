"""Support KNX devices."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from pathlib import Path

import voluptuous as vol
from xknx import XKNX
from xknx.core import XknxConnectionState
from xknx.core.telegram_queue import TelegramQueue
from xknx.dpt import DPTBase
from xknx.exceptions import ConversionError, CouldNotParseTelegram, XKNXException
from xknx.io import ConnectionConfig, ConnectionType, SecureConfig
from xknx.telegram import AddressFilter, Telegram
from xknx.telegram.address import DeviceGroupAddress, GroupAddress, InternalGroupAddress
from xknx.telegram.apci import GroupValueResponse, GroupValueWrite

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_EVENT,
    CONF_HOST,
    CONF_PORT,
    CONF_TYPE,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.reload import async_integration_yaml_config
from homeassistant.helpers.storage import STORAGE_DIR
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_KNX_CONNECTION_TYPE,
    CONF_KNX_EXPOSE,
    CONF_KNX_INDIVIDUAL_ADDRESS,
    CONF_KNX_KNXKEY_FILENAME,
    CONF_KNX_KNXKEY_PASSWORD,
    CONF_KNX_LOCAL_IP,
    CONF_KNX_MCAST_GRP,
    CONF_KNX_MCAST_PORT,
    CONF_KNX_RATE_LIMIT,
    CONF_KNX_ROUTE_BACK,
    CONF_KNX_ROUTING,
    CONF_KNX_ROUTING_BACKBONE_KEY,
    CONF_KNX_ROUTING_SECURE,
    CONF_KNX_ROUTING_SYNC_LATENCY_TOLERANCE,
    CONF_KNX_SECURE_DEVICE_AUTHENTICATION,
    CONF_KNX_SECURE_USER_ID,
    CONF_KNX_SECURE_USER_PASSWORD,
    CONF_KNX_STATE_UPDATER,
    CONF_KNX_TELEGRAM_LOG_SIZE,
    CONF_KNX_TUNNELING,
    CONF_KNX_TUNNELING_TCP,
    CONF_KNX_TUNNELING_TCP_SECURE,
    DATA_HASS_CONFIG,
    DATA_KNX_CONFIG,
    DOMAIN,
    KNX_ADDRESS,
    SUPPORTED_PLATFORMS_UI,
    SUPPORTED_PLATFORMS_YAML,
    TELEGRAM_LOG_DEFAULT,
)
from .device import KNXInterfaceDevice
from .expose import KNXExposeSensor, KNXExposeTime, create_knx_exposure
from .project import STORAGE_KEY as PROJECT_STORAGE_KEY, KNXProject
from .schema import (
    BinarySensorSchema,
    ButtonSchema,
    ClimateSchema,
    CoverSchema,
    DateSchema,
    DateTimeSchema,
    EventSchema,
    ExposeSchema,
    FanSchema,
    LightSchema,
    NotifySchema,
    NumberSchema,
    SceneSchema,
    SelectSchema,
    SensorSchema,
    SwitchSchema,
    TextSchema,
    TimeSchema,
    WeatherSchema,
)
from .services import register_knx_services
from .storage.config_store import KNXConfigStore
from .telegrams import STORAGE_KEY as TELEGRAMS_STORAGE_KEY, Telegrams
from .websocket import register_panel

_LOGGER = logging.getLogger(__name__)


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            # deprecated since 2021.12
            cv.deprecated(CONF_KNX_STATE_UPDATER),
            cv.deprecated(CONF_KNX_RATE_LIMIT),
            cv.deprecated(CONF_KNX_ROUTING),
            cv.deprecated(CONF_KNX_TUNNELING),
            cv.deprecated(CONF_KNX_INDIVIDUAL_ADDRESS),
            cv.deprecated(CONF_KNX_MCAST_GRP),
            cv.deprecated(CONF_KNX_MCAST_PORT),
            cv.deprecated("event_filter"),
            # deprecated since 2021.4
            cv.deprecated("config_file"),
            # deprecated since 2021.2
            cv.deprecated("fire_event"),
            cv.deprecated("fire_event_filter"),
            vol.Schema(
                {
                    **EventSchema.SCHEMA,
                    **ExposeSchema.platform_node(),
                    **BinarySensorSchema.platform_node(),
                    **ButtonSchema.platform_node(),
                    **ClimateSchema.platform_node(),
                    **CoverSchema.platform_node(),
                    **DateSchema.platform_node(),
                    **DateTimeSchema.platform_node(),
                    **FanSchema.platform_node(),
                    **LightSchema.platform_node(),
                    **NotifySchema.platform_node(),
                    **NumberSchema.platform_node(),
                    **SceneSchema.platform_node(),
                    **SelectSchema.platform_node(),
                    **SensorSchema.platform_node(),
                    **SwitchSchema.platform_node(),
                    **TextSchema.platform_node(),
                    **TimeSchema.platform_node(),
                    **WeatherSchema.platform_node(),
                }
            ),
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Start the KNX integration."""
    hass.data[DATA_HASS_CONFIG] = config
    conf: ConfigType | None = config.get(DOMAIN)

    if conf is None:
        # If we have a config entry, setup is done by that config entry.
        # If there is no config entry, this should fail.
        return bool(hass.config_entries.async_entries(DOMAIN))

    conf = dict(conf)
    hass.data[DATA_KNX_CONFIG] = conf

    register_knx_services(hass)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Load a config entry."""
    # `config` is None when reloading the integration
    # or no `knx` key in configuration.yaml
    if (config := hass.data.get(DATA_KNX_CONFIG)) is None:
        _conf = await async_integration_yaml_config(hass, DOMAIN)
        if not _conf or DOMAIN not in _conf:
            _LOGGER.warning(
                "No `knx:` key found in configuration.yaml. See "
                "https://www.home-assistant.io/integrations/knx/ "
                "for KNX entity configuration documentation"
            )
            # generate defaults
            config = CONFIG_SCHEMA({DOMAIN: {}})[DOMAIN]
        else:
            config = _conf[DOMAIN]
    try:
        knx_module = KNXModule(hass, config, entry)
        await knx_module.start()
    except XKNXException as ex:
        raise ConfigEntryNotReady from ex

    hass.data[DATA_KNX_CONFIG] = config
    hass.data[DOMAIN] = knx_module

    if CONF_KNX_EXPOSE in config:
        for expose_config in config[CONF_KNX_EXPOSE]:
            knx_module.exposures.append(
                create_knx_exposure(hass, knx_module.xknx, expose_config)
            )
    await hass.config_entries.async_forward_entry_setups(
        entry,
        {
            Platform.SENSOR,  # always forward sensor for system entities (telegram counter, etc.)
            *SUPPORTED_PLATFORMS_UI,  # forward all platforms that support UI entity management
            *{  # forward yaml-only managed platforms on demand
                platform for platform in SUPPORTED_PLATFORMS_YAML if platform in config
            },
        },
    )

    # set up notify service for backwards compatibility - remove 2024.11
    if NotifySchema.PLATFORM in config:
        hass.async_create_task(
            discovery.async_load_platform(
                hass, Platform.NOTIFY, DOMAIN, {}, hass.data[DATA_HASS_CONFIG]
            )
        )

    await register_panel(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unloading the KNX platforms."""
    #  if not loaded directly return
    if not hass.data.get(DOMAIN):
        return True

    knx_module: KNXModule = hass.data[DOMAIN]
    for exposure in knx_module.exposures:
        exposure.shutdown()

    unload_ok = await hass.config_entries.async_unload_platforms(
        entry,
        {
            Platform.SENSOR,  # always unload system entities (telegram counter, etc.)
            *SUPPORTED_PLATFORMS_UI,  # unload all platforms that support UI entity management
            *{  # unload yaml-only managed platforms if configured
                platform
                for platform in SUPPORTED_PLATFORMS_YAML
                if platform in hass.data[DATA_KNX_CONFIG]
            },
        },
    )
    if unload_ok:
        await knx_module.stop()
        hass.data.pop(DOMAIN)
        hass.data.pop(DATA_KNX_CONFIG)

    return unload_ok


async def async_update_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update a given config entry."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove a config entry."""

    def remove_files(storage_dir: Path, knxkeys_filename: str | None) -> None:
        """Remove KNX files."""
        if knxkeys_filename is not None:
            with contextlib.suppress(FileNotFoundError):
                (storage_dir / knxkeys_filename).unlink()
        with contextlib.suppress(FileNotFoundError):
            (storage_dir / PROJECT_STORAGE_KEY).unlink()
        with contextlib.suppress(FileNotFoundError):
            (storage_dir / TELEGRAMS_STORAGE_KEY).unlink()
        with contextlib.suppress(FileNotFoundError, OSError):
            (storage_dir / DOMAIN).rmdir()

    storage_dir = Path(hass.config.path(STORAGE_DIR))
    knxkeys_filename = entry.data.get(CONF_KNX_KNXKEY_FILENAME)
    await hass.async_add_executor_job(remove_files, storage_dir, knxkeys_filename)


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Remove a config entry from a device."""
    knx_module: KNXModule = hass.data[DOMAIN]
    if not device_entry.identifiers.isdisjoint(
        knx_module.interface_device.device_info["identifiers"]
    ):
        # can not remove interface device
        return False
    for entity in knx_module.config_store.get_entity_entries():
        if entity.device_id == device_entry.id:
            await knx_module.config_store.delete_entity(entity.entity_id)
    return True


class KNXModule:
    """Representation of KNX Object."""

    def __init__(
        self, hass: HomeAssistant, config: ConfigType, entry: ConfigEntry
    ) -> None:
        """Initialize KNX module."""
        self.hass = hass
        self.config = config
        self.connected = False
        self.exposures: list[KNXExposeSensor | KNXExposeTime] = []
        self.service_exposures: dict[str, KNXExposeSensor | KNXExposeTime] = {}
        self.entry = entry

        self.project = KNXProject(hass=hass, entry=entry)
        self.config_store = KNXConfigStore(hass=hass, entry=entry)

        self.xknx = XKNX(
            connection_config=self.connection_config(),
            rate_limit=self.entry.data[CONF_KNX_RATE_LIMIT],
            state_updater=self.entry.data[CONF_KNX_STATE_UPDATER],
        )
        self.xknx.connection_manager.register_connection_state_changed_cb(
            self.connection_state_changed_cb
        )
        self.telegrams = Telegrams(
            hass=hass,
            xknx=self.xknx,
            project=self.project,
            log_size=entry.data.get(CONF_KNX_TELEGRAM_LOG_SIZE, TELEGRAM_LOG_DEFAULT),
        )
        self.interface_device = KNXInterfaceDevice(
            hass=hass, entry=entry, xknx=self.xknx
        )

        self._address_filter_transcoder: dict[AddressFilter, type[DPTBase]] = {}
        self.group_address_transcoder: dict[DeviceGroupAddress, type[DPTBase]] = {}
        self.knx_event_callback: TelegramQueue.Callback = self.register_event_callback()

        self.entry.async_on_unload(
            self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self.stop)
        )
        self.entry.async_on_unload(self.entry.add_update_listener(async_update_entry))

    async def start(self) -> None:
        """Start XKNX object. Connect to tunneling or Routing device."""
        await self.project.load_project()
        await self.config_store.load_data()
        await self.telegrams.load_history()
        await self.xknx.start()

    async def stop(self, event: Event | None = None) -> None:
        """Stop XKNX object. Disconnect from tunneling or Routing device."""
        await self.xknx.stop()
        await self.telegrams.save_history()

    def connection_config(self) -> ConnectionConfig:
        """Return the connection_config."""
        _conn_type: str = self.entry.data[CONF_KNX_CONNECTION_TYPE]
        _knxkeys_file: str | None = (
            self.hass.config.path(
                STORAGE_DIR,
                self.entry.data[CONF_KNX_KNXKEY_FILENAME],
            )
            if self.entry.data.get(CONF_KNX_KNXKEY_FILENAME) is not None
            else None
        )
        if _conn_type == CONF_KNX_ROUTING:
            return ConnectionConfig(
                connection_type=ConnectionType.ROUTING,
                individual_address=self.entry.data[CONF_KNX_INDIVIDUAL_ADDRESS],
                multicast_group=self.entry.data[CONF_KNX_MCAST_GRP],
                multicast_port=self.entry.data[CONF_KNX_MCAST_PORT],
                local_ip=self.entry.data.get(CONF_KNX_LOCAL_IP),
                auto_reconnect=True,
                secure_config=SecureConfig(
                    knxkeys_password=self.entry.data.get(CONF_KNX_KNXKEY_PASSWORD),
                    knxkeys_file_path=_knxkeys_file,
                ),
                threaded=True,
            )
        if _conn_type == CONF_KNX_TUNNELING:
            return ConnectionConfig(
                connection_type=ConnectionType.TUNNELING,
                gateway_ip=self.entry.data[CONF_HOST],
                gateway_port=self.entry.data[CONF_PORT],
                local_ip=self.entry.data.get(CONF_KNX_LOCAL_IP),
                route_back=self.entry.data.get(CONF_KNX_ROUTE_BACK, False),
                auto_reconnect=True,
                secure_config=SecureConfig(
                    knxkeys_password=self.entry.data.get(CONF_KNX_KNXKEY_PASSWORD),
                    knxkeys_file_path=_knxkeys_file,
                ),
                threaded=True,
            )
        if _conn_type == CONF_KNX_TUNNELING_TCP:
            return ConnectionConfig(
                connection_type=ConnectionType.TUNNELING_TCP,
                gateway_ip=self.entry.data[CONF_HOST],
                gateway_port=self.entry.data[CONF_PORT],
                auto_reconnect=True,
                secure_config=SecureConfig(
                    knxkeys_password=self.entry.data.get(CONF_KNX_KNXKEY_PASSWORD),
                    knxkeys_file_path=_knxkeys_file,
                ),
                threaded=True,
            )
        if _conn_type == CONF_KNX_TUNNELING_TCP_SECURE:
            return ConnectionConfig(
                connection_type=ConnectionType.TUNNELING_TCP_SECURE,
                gateway_ip=self.entry.data[CONF_HOST],
                gateway_port=self.entry.data[CONF_PORT],
                secure_config=SecureConfig(
                    user_id=self.entry.data.get(CONF_KNX_SECURE_USER_ID),
                    user_password=self.entry.data.get(CONF_KNX_SECURE_USER_PASSWORD),
                    device_authentication_password=self.entry.data.get(
                        CONF_KNX_SECURE_DEVICE_AUTHENTICATION
                    ),
                    knxkeys_password=self.entry.data.get(CONF_KNX_KNXKEY_PASSWORD),
                    knxkeys_file_path=_knxkeys_file,
                ),
                auto_reconnect=True,
                threaded=True,
            )
        if _conn_type == CONF_KNX_ROUTING_SECURE:
            return ConnectionConfig(
                connection_type=ConnectionType.ROUTING_SECURE,
                individual_address=self.entry.data[CONF_KNX_INDIVIDUAL_ADDRESS],
                multicast_group=self.entry.data[CONF_KNX_MCAST_GRP],
                multicast_port=self.entry.data[CONF_KNX_MCAST_PORT],
                local_ip=self.entry.data.get(CONF_KNX_LOCAL_IP),
                secure_config=SecureConfig(
                    backbone_key=self.entry.data.get(CONF_KNX_ROUTING_BACKBONE_KEY),
                    latency_ms=self.entry.data.get(
                        CONF_KNX_ROUTING_SYNC_LATENCY_TOLERANCE
                    ),
                    knxkeys_password=self.entry.data.get(CONF_KNX_KNXKEY_PASSWORD),
                    knxkeys_file_path=_knxkeys_file,
                ),
                auto_reconnect=True,
                threaded=True,
            )
        return ConnectionConfig(
            auto_reconnect=True,
            secure_config=SecureConfig(
                knxkeys_password=self.entry.data.get(CONF_KNX_KNXKEY_PASSWORD),
                knxkeys_file_path=_knxkeys_file,
            ),
            threaded=True,
        )

    async def connection_state_changed_cb(self, state: XknxConnectionState) -> None:
        """Call invoked after a KNX connection state change was received."""
        self.connected = state == XknxConnectionState.CONNECTED
        if tasks := [device.after_update() for device in self.xknx.devices]:
            await asyncio.gather(*tasks)

    async def telegram_received_cb(self, telegram: Telegram) -> None:
        """Call invoked after a KNX telegram was received."""
        # Not all telegrams have serializable data.
        data: int | tuple[int, ...] | None = None
        value = None
        if (
            isinstance(telegram.payload, (GroupValueWrite, GroupValueResponse))
            and telegram.payload.value is not None
            and isinstance(
                telegram.destination_address, (GroupAddress, InternalGroupAddress)
            )
        ):
            data = telegram.payload.value.value
            if transcoder := (
                self.group_address_transcoder.get(telegram.destination_address)
                or next(
                    (
                        _transcoder
                        for _filter, _transcoder in self._address_filter_transcoder.items()
                        if _filter.match(telegram.destination_address)
                    ),
                    None,
                )
            ):
                try:
                    value = transcoder.from_knx(telegram.payload.value)
                except (ConversionError, CouldNotParseTelegram) as err:
                    _LOGGER.warning(
                        (
                            "Error in `knx_event` at decoding type '%s' from"
                            " telegram %s\n%s"
                        ),
                        transcoder.__name__,
                        telegram,
                        err,
                    )

        self.hass.bus.async_fire(
            "knx_event",
            {
                "data": data,
                "destination": str(telegram.destination_address),
                "direction": telegram.direction.value,
                "value": value,
                "source": str(telegram.source_address),
                "telegramtype": telegram.payload.__class__.__name__,
            },
        )

    def register_event_callback(self) -> TelegramQueue.Callback:
        """Register callback for knx_event within XKNX TelegramQueue."""
        address_filters = []
        for filter_set in self.config[CONF_EVENT]:
            _filters = list(map(AddressFilter, filter_set[KNX_ADDRESS]))
            address_filters.extend(_filters)
            if (dpt := filter_set.get(CONF_TYPE)) and (
                transcoder := DPTBase.parse_transcoder(dpt)
            ):
                self._address_filter_transcoder.update(
                    {
                        _filter: transcoder  # type: ignore[type-abstract]
                        for _filter in _filters
                    }
                )

        return self.xknx.telegram_queue.register_telegram_received_cb(
            self.telegram_received_cb,
            address_filters=address_filters,
            group_addresses=[],
            match_for_outgoing=True,
        )
