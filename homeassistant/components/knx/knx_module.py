"""KNX Module for Home Assistant."""

import logging

from xknx import XKNX
from xknx.core import XknxConnectionState
from xknx.core.state_updater import StateTrackerType, TrackerOptions
from xknx.core.telegram_queue import TelegramQueue
from xknx.dpt import DPTBase
from xknx.exceptions import ConversionError, CouldNotParseTelegram
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
)
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers.storage import STORAGE_DIR
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_KNX_CONNECTION_TYPE,
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
    CONF_KNX_TUNNEL_ENDPOINT_IA,
    CONF_KNX_TUNNELING,
    CONF_KNX_TUNNELING_TCP,
    CONF_KNX_TUNNELING_TCP_SECURE,
    KNX_ADDRESS,
    TELEGRAM_LOG_DEFAULT,
)
from .device import KNXInterfaceDevice
from .expose import KNXExposeSensor, KNXExposeTime
from .project import KNXProject
from .storage.config_store import KNXConfigStore
from .telegrams import Telegrams

_LOGGER = logging.getLogger(__name__)


class KNXModule:
    """Representation of KNX Object."""

    def __init__(
        self, hass: HomeAssistant, config: ConfigType, entry: ConfigEntry
    ) -> None:
        """Initialize KNX module."""
        self.hass = hass
        self.config_yaml = config
        self.connected = False
        self.exposures: list[KNXExposeSensor | KNXExposeTime] = []
        self.service_exposures: dict[str, KNXExposeSensor | KNXExposeTime] = {}
        self.entry = entry

        self.project = KNXProject(hass=hass, entry=entry)
        self.config_store = KNXConfigStore(hass=hass, config_entry=entry)

        default_state_updater = (
            TrackerOptions(tracker_type=StateTrackerType.EXPIRE, update_interval_min=60)
            if self.entry.data[CONF_KNX_STATE_UPDATER]
            else TrackerOptions(
                tracker_type=StateTrackerType.INIT, update_interval_min=60
            )
        )
        self.xknx = XKNX(
            address_format=self.project.get_address_format(),
            connection_config=self.connection_config(),
            rate_limit=self.entry.data[CONF_KNX_RATE_LIMIT],
            state_updater=default_state_updater,
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

    async def start(self) -> None:
        """Start XKNX object. Connect to tunneling or Routing device."""
        await self.project.load_project(self.xknx)
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
                individual_address=self.entry.data.get(CONF_KNX_TUNNEL_ENDPOINT_IA),
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
                individual_address=self.entry.data.get(CONF_KNX_TUNNEL_ENDPOINT_IA),
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
            individual_address=self.entry.data.get(
                CONF_KNX_TUNNEL_ENDPOINT_IA,  # may be configured at knxkey upload
            ),
            secure_config=SecureConfig(
                knxkeys_password=self.entry.data.get(CONF_KNX_KNXKEY_PASSWORD),
                knxkeys_file_path=_knxkeys_file,
            ),
            threaded=True,
        )

    def connection_state_changed_cb(self, state: XknxConnectionState) -> None:
        """Call invoked after a KNX connection state change was received."""
        self.connected = state == XknxConnectionState.CONNECTED
        for device in self.xknx.devices:
            device.after_update()

    def telegram_received_cb(self, telegram: Telegram) -> None:
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
        for filter_set in self.config_yaml[CONF_EVENT]:
            _filters = list(map(AddressFilter, filter_set[KNX_ADDRESS]))
            address_filters.extend(_filters)
            if (dpt := filter_set.get(CONF_TYPE)) and (
                transcoder := DPTBase.parse_transcoder(dpt)
            ):
                self._address_filter_transcoder.update(
                    {_filter: transcoder for _filter in _filters}
                )

        return self.xknx.telegram_queue.register_telegram_received_cb(
            self.telegram_received_cb,
            address_filters=address_filters,
            group_addresses=[],
            match_for_outgoing=True,
        )
