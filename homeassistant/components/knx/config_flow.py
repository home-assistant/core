"""Config flow for KNX."""

import asyncio
from collections.abc import AsyncGenerator, Mapping
from typing import TYPE_CHECKING, Any, Final, Literal, NamedTuple, override
from urllib.parse import quote, unquote, urlparse, urlunparse

from knx_telegram_store import ConnectionErrorKind
from knx_telegram_store.backends.postgres import PostgresStore
import probatio
from xknx import XKNX
from xknx.exceptions.exception import (
    CommunicationError,
    InvalidSecureConfiguration,
    XKNXException,
)
from xknx.io import DEFAULT_MCAST_GRP, DEFAULT_MCAST_PORT
from xknx.io.gateway_scanner import GatewayDescriptor, GatewayScanner
from xknx.io.self_description import request_description
from xknx.io.util import validate_ip as xknx_validate_ip
from xknx.secure.keyring import Keyring, XMLInterface

from homeassistant import data_entry_flow
from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.field_visibility import FieldCondition
from homeassistant.helpers.typing import Undefined, VolDictType

from .const import (
    CONF_KNX_AUTOMATIC,
    CONF_KNX_CONNECTION_TYPE,
    CONF_KNX_DEFAULT_RATE_LIMIT,
    CONF_KNX_DEFAULT_STATE_UPDATER,
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
    CONF_KNX_TELEGRAM_DB_BACKEND,
    CONF_KNX_TELEGRAM_DB_DATABASE,
    CONF_KNX_TELEGRAM_DB_HOST,
    CONF_KNX_TELEGRAM_DB_LOAD_HOURS,
    CONF_KNX_TELEGRAM_DB_PASSWORD,
    CONF_KNX_TELEGRAM_DB_PORT,
    CONF_KNX_TELEGRAM_DB_POSTGRES_DSN,
    CONF_KNX_TELEGRAM_DB_RETENTION_DAYS,
    CONF_KNX_TELEGRAM_DB_TLS,
    CONF_KNX_TELEGRAM_DB_USER,
    CONF_KNX_TUNNEL_ENDPOINT_IA,
    CONF_KNX_TUNNELING,
    CONF_KNX_TUNNELING_TCP,
    CONF_KNX_TUNNELING_TCP_SECURE,
    DEFAULT_ROUTING_IA,
    DOMAIN,
    KNX_MODULE_KEY,
    KNX_TELEGRAM_BACKEND_POSTGRES,
    KNX_TELEGRAM_BACKEND_SQLITE,
    KNX_TELEGRAM_DB_RETENTION_DEFAULT,
    KNX_TELEGRAM_LOAD_HOURS_DEFAULT,
    KNXConfigEntryData,
    KNXConfigEntryOptions,
)
from .storage.keyring import (
    DEFAULT_KNX_KEYRING_FILENAME,
    load_stored_knxkeys_file,
    save_uploaded_knxkeys_file,
)
from .validation import ia_validator, ip_v4_validator

CONF_KNX_GATEWAY: Final = "gateway"
CONF_MAX_RATE_LIMIT: Final = 60

DEFAULT_ENTRY_DATA = KNXConfigEntryData(
    individual_address=DEFAULT_ROUTING_IA,
    local_ip=None,
    multicast_group=DEFAULT_MCAST_GRP,
    multicast_port=DEFAULT_MCAST_PORT,
    route_back=False,
)

DEFAULT_ENTRY_OPTIONS = KNXConfigEntryOptions(
    rate_limit=CONF_KNX_DEFAULT_RATE_LIMIT,
    state_updater=CONF_KNX_DEFAULT_STATE_UPDATER,
    telegram_db_retention_days=KNX_TELEGRAM_DB_RETENTION_DEFAULT,
    telegram_db_load_hours=KNX_TELEGRAM_LOAD_HOURS_DEFAULT,
    telegram_db_backend=KNX_TELEGRAM_BACKEND_SQLITE,
)

CONF_KEYRING_FILE: Final = "knxkeys_file"

CONF_KNX_TELEGRAM_STORE_SECTION: Final = "telegram_store_section"

# Timeout for the PostgreSQL connection check, so an unreachable host cannot
# block the options flow until the driver/OS connection timeout expires.
DSN_CHECK_TIMEOUT = 10

CONF_KNX_TUNNELING_TYPE: Final = "tunneling_type"
CONF_KNX_TUNNELING_TYPE_LABELS: Final = {
    CONF_KNX_TUNNELING: "UDP (Tunneling v1)",
    CONF_KNX_TUNNELING_TCP: "TCP (Tunneling v2)",
    CONF_KNX_TUNNELING_TCP_SECURE: "Secure Tunneling (TCP)",
}

OPTION_MANUAL_TUNNEL: Final = "Manual"

CONF_KNX_SECURE_KEY_SOURCE: Final = "key_source"
KEY_SOURCE_KNXKEYS_EXISTING: Final = "knxkeys_existing"
KEY_SOURCE_KNXKEYS_UPLOAD: Final = "knxkeys_upload"
KEY_SOURCE_MANUAL: Final = "manual"

_KEYRING_UPLOAD_VISIBLE: Final[FieldCondition] = {
    "field": CONF_KNX_SECURE_KEY_SOURCE,
    "value": KEY_SOURCE_KNXKEYS_UPLOAD,
}
_MANUAL_KEYS_VISIBLE: Final[FieldCondition] = {
    "field": CONF_KNX_SECURE_KEY_SOURCE,
    "value": KEY_SOURCE_MANUAL,
}

_IA_SELECTOR = selector.TextSelector()
_IP_SELECTOR = selector.TextSelector()
_PORT_SELECTOR = probatio.All(
    selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=1, max=65535, mode=selector.NumberSelectorMode.BOX
        ),
    ),
    probatio.Coerce(int),
)
_PASSWORD_SELECTOR = selector.TextSelector(
    selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD),
)


class StoredKeyring(NamedTuple):
    """Keyring file stored by a previous import."""

    keyring: Keyring
    filename: str
    password: str


def _describe_connection(data: Mapping[str, Any]) -> str:
    """Return a human readable description of a configured connection."""
    connection_type = data.get(CONF_KNX_CONNECTION_TYPE)
    if connection_type in CONF_KNX_TUNNELING_TYPE_LABELS:
        description = (
            f"{CONF_KNX_TUNNELING_TYPE_LABELS[connection_type]}"
            f" @ {data[CONF_HOST]}:{data[CONF_PORT]}"
        )
        if tunnel_endpoint_ia := data.get(CONF_KNX_TUNNEL_ENDPOINT_IA):
            description += f" as {tunnel_endpoint_ia}"
        return description
    if connection_type == CONF_KNX_ROUTING:
        return f"Routing as {data[CONF_KNX_INDIVIDUAL_ADDRESS]}"
    if connection_type == CONF_KNX_ROUTING_SECURE:
        return f"Secure Routing as {data[CONF_KNX_INDIVIDUAL_ADDRESS]}"
    return CONF_KNX_AUTOMATIC.capitalize()


class KNXConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a KNX config flow."""

    VERSION = 2
    MINOR_VERSION = 2

    def __init__(self) -> None:
        """Initialize KNX config flow."""
        self.initial_data = DEFAULT_ENTRY_DATA
        self.new_entry_data = KNXConfigEntryData()
        self.new_title: str | None = None

        self._keyring: Keyring | None = None
        self._stored_keyring: StoredKeyring | None = None
        self._stored_keyring_loaded = False
        self._found_gateways: list[GatewayDescriptor] = []
        self._found_tunnels: list[GatewayDescriptor] = []
        self._selected_tunnel: GatewayDescriptor | None = None
        self._tunnel_endpoints: list[XMLInterface] = []

        self._gatewayscanner: GatewayScanner | None = None
        self._async_scan_gen: AsyncGenerator[GatewayDescriptor] | None = None

    @staticmethod
    @callback
    @override
    def async_get_options_flow(config_entry: ConfigEntry) -> KNXOptionsFlow:
        """Get the options flow for this handler."""
        return KNXOptionsFlow(config_entry)

    @property
    def _xknx(self) -> XKNX:
        """Return XKNX instance."""
        if (self.source == SOURCE_RECONFIGURE) and (
            knx_module := self.hass.data.get(KNX_MODULE_KEY)
        ):
            return knx_module.xknx
        return XKNX()

    @property
    def connection_type(self) -> str:
        """Return the configured connection type."""
        _new_type = self.new_entry_data.get(CONF_KNX_CONNECTION_TYPE)
        if _new_type is None:
            return self.initial_data[CONF_KNX_CONNECTION_TYPE]
        return _new_type

    @property
    def tunnel_endpoint_ia(self) -> str | None:
        """Return the configured tunnel endpoint individual address."""
        return self.new_entry_data.get(
            CONF_KNX_TUNNEL_ENDPOINT_IA,
            self.initial_data.get(CONF_KNX_TUNNEL_ENDPOINT_IA),
        )

    @callback
    def finish_flow(self) -> ConfigFlowResult:
        """Create or update the ConfigEntry."""
        if self.source == SOURCE_RECONFIGURE:
            entry = self._get_reconfigure_entry()
            _tunnel_endpoint_str = self.initial_data.get(
                CONF_KNX_TUNNEL_ENDPOINT_IA, "Tunneling"
            )
            if self.new_title and not entry.title.startswith(
                # Overwrite standard titles, but not user defined ones
                (
                    f"KNX {self.initial_data[CONF_KNX_CONNECTION_TYPE]}",
                    CONF_KNX_AUTOMATIC.capitalize(),
                    "Tunneling @ ",
                    f"{_tunnel_endpoint_str} @",
                    "Tunneling UDP @ ",
                    "Tunneling TCP @ ",
                    "Secure Tunneling",
                    "Routing as ",
                    "Secure Routing as ",
                )
            ):
                self.new_title = None
            return self.async_update_reload_and_abort(
                self._get_reconfigure_entry(),
                data_updates=self.new_entry_data,
                title=self.new_title or Undefined,
            )

        title = self.new_title or f"KNX {self.new_entry_data[CONF_KNX_CONNECTION_TYPE]}"
        return self.async_create_entry(
            title=title,
            data=DEFAULT_ENTRY_DATA | self.new_entry_data,
            options=DEFAULT_ENTRY_OPTIONS,
        )

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        return await self.async_step_connection_type()

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of existing entry."""
        entry = self._get_reconfigure_entry()
        self.initial_data = dict(entry.data)  # type: ignore[assignment]
        if (stored_keyring := await self._async_get_stored_keyring()) is not None:
            keyring_project = stored_keyring.keyring.project_name
        else:
            keyring_project = self.initial_data.get(CONF_KNX_KNXKEY_FILENAME) or "-"
        return self.async_show_menu(
            step_id="reconfigure",
            menu_options=[
                "connection_type",
                "secure_knxkeys",
            ],
            description_placeholders={
                "current_connection": _describe_connection(self.initial_data),
                "keyring_project": keyring_project,
            },
        )

    async def async_step_connection_type(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Handle connection type configuration."""
        if user_input is not None:
            if self._async_scan_gen:
                await self._async_scan_gen.aclose()  # stop the scan
                self._async_scan_gen = None
            if self._gatewayscanner:
                self._found_gateways = list(
                    self._gatewayscanner.found_gateways.values()
                )
            connection_type = user_input[CONF_KNX_CONNECTION_TYPE]
            if connection_type == CONF_KNX_ROUTING:
                return await self.async_step_routing()

            if connection_type == CONF_KNX_TUNNELING:
                self._found_tunnels = [
                    gateway
                    for gateway in self._found_gateways
                    if gateway.supports_tunnelling
                ]
                self._found_tunnels.sort(
                    key=lambda tunnel: (
                        tunnel.individual_address.raw
                        if tunnel.individual_address
                        else 0
                    )
                )
                return await self.async_step_tunnel()

            # Automatic connection type
            self.new_entry_data = KNXConfigEntryData(
                connection_type=CONF_KNX_AUTOMATIC,
                tunnel_endpoint_ia=None,
            )
            self.new_title = CONF_KNX_AUTOMATIC.capitalize()
            return self.finish_flow()

        supported_connection_types = [CONF_KNX_TUNNELING, CONF_KNX_ROUTING]

        self._gatewayscanner = GatewayScanner(
            self._xknx, stop_on_found=0, timeout_in_seconds=2
        )
        # keep a reference to the generator to scan in
        # background until user selects a connection type
        self._async_scan_gen = self._gatewayscanner.async_scan()
        try:
            await anext(self._async_scan_gen)
        except StopAsyncIteration:
            pass  # scan finished, no interfaces discovered
        else:
            # add automatic at first position only if a gateway responded
            supported_connection_types.insert(0, CONF_KNX_AUTOMATIC)

        default_connection_type: Literal["automatic", "tunneling", "routing"]
        _current_conn = self.initial_data.get(CONF_KNX_CONNECTION_TYPE)
        if _current_conn in (
            CONF_KNX_TUNNELING,
            CONF_KNX_TUNNELING_TCP,
            CONF_KNX_TUNNELING_TCP_SECURE,
        ):
            default_connection_type = CONF_KNX_TUNNELING
        elif _current_conn in (CONF_KNX_ROUTING, CONF_KNX_ROUTING_SECURE):
            default_connection_type = CONF_KNX_ROUTING
        elif CONF_KNX_AUTOMATIC in supported_connection_types:
            default_connection_type = CONF_KNX_AUTOMATIC
        else:
            default_connection_type = CONF_KNX_TUNNELING

        fields = {
            probatio.Required(
                CONF_KNX_CONNECTION_TYPE, default=default_connection_type
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=supported_connection_types,
                    mode=selector.SelectSelectorMode.LIST,
                    translation_key="connection_type",
                )
            )
        }
        return self.async_show_form(
            step_id="connection_type", data_schema=probatio.Schema(fields)
        )

    async def async_step_tunnel(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Select a tunnel from a list.

        Will be skipped if the gateway scan was unsuccessful.
        """
        if user_input is not None:
            if user_input[CONF_KNX_GATEWAY] == OPTION_MANUAL_TUNNEL:
                if self._found_tunnels:
                    self._selected_tunnel = self._found_tunnels[0]
                return await self.async_step_manual_tunnel()

            self._selected_tunnel = next(
                tunnel
                for tunnel in self._found_tunnels
                if user_input[CONF_KNX_GATEWAY] == str(tunnel)
            )
            connection_type = (
                CONF_KNX_TUNNELING_TCP_SECURE
                if self._selected_tunnel.tunnelling_requires_secure
                else CONF_KNX_TUNNELING_TCP
                if self._selected_tunnel.supports_tunnelling_tcp
                else CONF_KNX_TUNNELING
            )
            self.new_entry_data = KNXConfigEntryData(
                host=self._selected_tunnel.ip_addr,
                port=self._selected_tunnel.port,
                route_back=False,
                connection_type=connection_type,
                device_authentication=None,
                user_id=None,
                user_password=None,
                tunnel_endpoint_ia=None,
            )
            if connection_type == CONF_KNX_TUNNELING_TCP:
                return await self.async_step_tcp_tunnel_endpoint()
            if connection_type == CONF_KNX_TUNNELING_TCP_SECURE:
                return await self.async_step_secure_tunnel()
            self.new_title = f"Tunneling @ {self._selected_tunnel}"
            return self.finish_flow()

        if not self._found_tunnels:
            return await self.async_step_manual_tunnel()

        tunnel_options = [
            selector.SelectOptionDict(
                value=str(tunnel),
                label=(
                    f"{tunnel}"
                    f"{' TCP' if tunnel.supports_tunnelling_tcp else ' UDP'}"
                    f"{
                        ' 🔐 Secure tunneling'
                        if tunnel.tunnelling_requires_secure
                        else ''
                    }"
                ),
            )
            for tunnel in self._found_tunnels
        ]
        tunnel_options.append(
            selector.SelectOptionDict(
                value=OPTION_MANUAL_TUNNEL, label=OPTION_MANUAL_TUNNEL
            )
        )
        default_tunnel = next(
            (
                str(tunnel)
                for tunnel in self._found_tunnels
                if tunnel.ip_addr == self.initial_data.get(CONF_HOST)
            ),
            probatio.UNDEFINED,
        )
        fields = {
            probatio.Required(
                CONF_KNX_GATEWAY, default=default_tunnel
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=tunnel_options,
                    mode=selector.SelectSelectorMode.LIST,
                )
            )
        }
        return self.async_show_form(
            step_id="tunnel", data_schema=probatio.Schema(fields)
        )

    async def async_step_tcp_tunnel_endpoint(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Select specific tunnel endpoint for plain TCP connection."""
        if user_input is not None:
            selected_tunnel_ia: str | None = (
                None
                if user_input[CONF_KNX_TUNNEL_ENDPOINT_IA] == CONF_KNX_AUTOMATIC
                else user_input[CONF_KNX_TUNNEL_ENDPOINT_IA]
            )
            self.new_entry_data |= KNXConfigEntryData(
                tunnel_endpoint_ia=selected_tunnel_ia,
            )
            self.new_title = (
                f"{selected_tunnel_ia or 'Tunneling'} @ {self._selected_tunnel}"
            )
            return self.finish_flow()

        # this step is only called from async_step_tunnel
        # so self._selected_tunnel is always set
        assert self._selected_tunnel
        # skip if only one tunnel endpoint or no tunnelling slot infos
        if len(self._selected_tunnel.tunnelling_slots) <= 1:
            return self.finish_flow()

        tunnel_endpoint_options = [
            selector.SelectOptionDict(
                value=CONF_KNX_AUTOMATIC, label=CONF_KNX_AUTOMATIC.capitalize()
            )
        ]
        _current_ia = self._xknx.current_address
        tunnel_endpoint_options.extend(
            selector.SelectOptionDict(
                value=str(slot),
                label=(
                    f"{slot} - {
                        'current connection'
                        if slot == _current_ia
                        else 'occupied'
                        if not slot_status.free
                        else 'free'
                    }"
                ),
            )
            for slot, slot_status in self._selected_tunnel.tunnelling_slots.items()
        )
        default_endpoint = (
            self.initial_data.get(CONF_KNX_TUNNEL_ENDPOINT_IA) or CONF_KNX_AUTOMATIC
        )
        return self.async_show_form(
            step_id="tcp_tunnel_endpoint",
            data_schema=probatio.Schema(
                {
                    probatio.Required(
                        CONF_KNX_TUNNEL_ENDPOINT_IA, default=default_endpoint
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=tunnel_endpoint_options,
                            mode=selector.SelectSelectorMode.LIST,
                        )
                    ),
                }
            ),
        )

    async def async_step_manual_tunnel(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Manually configure tunnel connection parameters.

        Fields default to preselected gateway if one was found.
        """
        errors: dict = {}

        if user_input is not None:
            try:
                _host = user_input[CONF_HOST]
                _host_ip = await xknx_validate_ip(_host)
                ip_v4_validator(_host_ip, multicast=False)
            except probatio.Invalid, XKNXException:
                errors[CONF_HOST] = "invalid_ip_address"

            _local_ip = None
            if _local := (user_input.get(CONF_KNX_LOCAL_IP) or None):
                try:
                    _local_ip = await xknx_validate_ip(_local)
                    ip_v4_validator(_local_ip, multicast=False)
                except probatio.Invalid, XKNXException:
                    errors[CONF_KNX_LOCAL_IP] = "invalid_ip_address"

            selected_tunneling_type = user_input[CONF_KNX_TUNNELING_TYPE]
            # hidden for TCP tunneling types
            route_back = user_input.get(CONF_KNX_ROUTE_BACK, False)
            if not errors:
                try:
                    self._selected_tunnel = await request_description(
                        gateway_ip=_host_ip,
                        gateway_port=user_input[CONF_PORT],
                        local_ip=_local_ip,
                        route_back=route_back,
                    )
                except CommunicationError:
                    errors["base"] = "cannot_connect"
                else:
                    if bool(self._selected_tunnel.tunnelling_requires_secure) is not (
                        selected_tunneling_type == CONF_KNX_TUNNELING_TCP_SECURE
                    ) or (
                        selected_tunneling_type == CONF_KNX_TUNNELING_TCP
                        and not self._selected_tunnel.supports_tunnelling_tcp
                    ):
                        errors[CONF_KNX_TUNNELING_TYPE] = "unsupported_tunnel_type"

            if not errors:
                self.new_entry_data = KNXConfigEntryData(
                    connection_type=selected_tunneling_type,
                    host=_host,
                    port=user_input[CONF_PORT],
                    route_back=route_back,
                    local_ip=_local,
                    device_authentication=None,
                    user_id=None,
                    user_password=None,
                    tunnel_endpoint_ia=None,
                )

                if selected_tunneling_type == CONF_KNX_TUNNELING_TCP_SECURE:
                    return await self.async_step_secure_tunnel()
                _proto = (
                    "UDP" if selected_tunneling_type == CONF_KNX_TUNNELING else "TCP"
                )
                self.new_title = f"Tunneling {_proto} @ {_host}"
                return self.finish_flow()

        _reconfiguring_existing_tunnel = (
            self.initial_data.get(CONF_KNX_CONNECTION_TYPE)
            in CONF_KNX_TUNNELING_TYPE_LABELS
        )
        ip_address: str | None
        if (  # initial attempt on ConfigFlow or coming from automatic / routing
            not _reconfiguring_existing_tunnel
            and not user_input
            and self._selected_tunnel is not None
        ):  # default to first found tunnel
            ip_address = self._selected_tunnel.ip_addr
            port = self._selected_tunnel.port
            if self._selected_tunnel.tunnelling_requires_secure:
                default_type = CONF_KNX_TUNNELING_TCP_SECURE
            elif self._selected_tunnel.supports_tunnelling_tcp:
                default_type = CONF_KNX_TUNNELING_TCP
            else:
                default_type = CONF_KNX_TUNNELING
        else:  # OptionFlow, no tunnel discovered or user input
            ip_address = (
                user_input[CONF_HOST]
                if user_input
                else self.initial_data.get(CONF_HOST)
            )
            port = (
                user_input[CONF_PORT]
                if user_input
                else self.initial_data.get(CONF_PORT, DEFAULT_MCAST_PORT)
            )
            default_type = (
                user_input[CONF_KNX_TUNNELING_TYPE]
                if user_input
                else self.initial_data[CONF_KNX_CONNECTION_TYPE]
                if _reconfiguring_existing_tunnel
                else CONF_KNX_TUNNELING
            )
        _route_back: bool = self.initial_data.get(
            CONF_KNX_ROUTE_BACK, not bool(self._selected_tunnel)
        )

        fields: VolDictType = {
            probatio.Required(
                CONF_KNX_TUNNELING_TYPE, default=default_type
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=list(CONF_KNX_TUNNELING_TYPE_LABELS),
                    mode=selector.SelectSelectorMode.LIST,
                    translation_key="tunneling_type",
                )
            ),
            probatio.Required(CONF_HOST, default=ip_address): _IP_SELECTOR,
            probatio.Required(CONF_PORT, default=port): _PORT_SELECTOR,
            data_entry_flow.Required(
                CONF_KNX_ROUTE_BACK,
                default=_route_back,
                visible={"field": CONF_KNX_TUNNELING_TYPE, "value": CONF_KNX_TUNNELING},
            ): selector.BooleanSelector(),
            probatio.Optional(CONF_KNX_LOCAL_IP): _IP_SELECTOR,
        }

        if not self._found_tunnels and not errors.get("base"):
            errors["base"] = "no_tunnel_discovered"
        return self.async_show_form(
            step_id="manual_tunnel", data_schema=probatio.Schema(fields), errors=errors
        )

    async def _async_get_stored_keyring(self) -> StoredKeyring | None:
        """Return the keyring imported by a previous flow if it can be loaded."""
        if self._stored_keyring_loaded:
            return self._stored_keyring
        self._stored_keyring_loaded = True
        filename = self.initial_data.get(CONF_KNX_KNXKEY_FILENAME)
        password = self.initial_data.get(CONF_KNX_KNXKEY_PASSWORD)
        if filename is None or password is None:
            return None
        try:
            keyring = await load_stored_knxkeys_file(self.hass, filename, password)
        except InvalidSecureConfiguration, FileNotFoundError:
            return None
        self._stored_keyring = StoredKeyring(keyring, filename, password)
        return self._stored_keyring

    def _validate_keyring(
        self, keyring: Keyring
    ) -> tuple[dict[str, str], dict[str, str]]:
        """Check that a keyring provides the keys for the configured connection.

        Return form errors and description placeholders.
        """
        if self.connection_type == CONF_KNX_ROUTING_SECURE and (
            keyring.backbone is None or keyring.backbone.decrypted_key is None
        ):
            return {"base": "keyfile_no_backbone_key"}, {}
        if (
            self._selected_tunnel is not None
            and (host_ia := self._selected_tunnel.individual_address)
            and not keyring.get_tunnel_interfaces_by_host(host=host_ia)
        ):
            return {"base": "keyfile_no_tunnel_for_host"}, {CONF_HOST: str(host_ia)}
        return {}, {}

    async def _async_keyring_selected(
        self, keyring: Keyring, filename: str, password: str
    ) -> ConfigFlowResult:
        """Store the keyring in the entry data and continue the flow."""
        self._keyring = keyring
        self.new_entry_data |= KNXConfigEntryData(
            knxkeys_filename=filename,
            knxkeys_password=password,
            backbone_key=None,
            sync_latency_tolerance=None,
        )
        if self.connection_type in (CONF_KNX_ROUTING, CONF_KNX_ROUTING_SECURE):
            return self.finish_flow()

        # Tunneling / Automatic
        # skip selection step if the keyring includes the configured tunnel
        if self.tunnel_endpoint_ia is not None and self.tunnel_endpoint_ia in [
            str(_if.individual_address) for _if in keyring.interfaces
        ]:
            return self.finish_flow()
        return await self.async_step_knxkeys_tunnel_select()

    async def _async_handle_keyring_source(
        self,
        key_source: str,
        user_input: dict[str, Any],
        errors: dict[str, str],
        description_placeholders: dict[str, str],
    ) -> ConfigFlowResult | None:
        """Continue the flow with the stored or uploaded keyring.

        Return None and fill `errors` if the keyring can't be used.
        """
        if key_source == KEY_SOURCE_KNXKEYS_EXISTING:
            if TYPE_CHECKING:
                # only offered when a stored keyring was loaded
                assert self._stored_keyring is not None
            keyring, filename, password = self._stored_keyring
        else:
            password = user_input[CONF_KNX_KNXKEY_PASSWORD]
            filename = f"{DOMAIN}/{DEFAULT_KNX_KEYRING_FILENAME}"
            try:
                keyring = await save_uploaded_knxkeys_file(
                    self.hass,
                    uploaded_file_id=user_input[CONF_KEYRING_FILE],
                    password=password,
                )
            except InvalidSecureConfiguration:
                errors[CONF_KNX_KNXKEY_PASSWORD] = "keyfile_invalid_signature"
                return None
            # the uploaded file replaced the stored one
            self._stored_keyring = StoredKeyring(keyring, filename, password)

        keyring_errors, keyring_placeholders = self._validate_keyring(keyring)
        if keyring_errors:
            errors.update(keyring_errors)
            description_placeholders.update(keyring_placeholders)
            return None
        return await self._async_keyring_selected(keyring, filename, password)

    async def _async_key_source_fields(self, manual_configured: bool) -> VolDictType:
        """Return the fields to select the IP Secure key source and upload a keyring."""
        sources = [KEY_SOURCE_KNXKEYS_UPLOAD, KEY_SOURCE_MANUAL]
        if await self._async_get_stored_keyring() is not None:
            sources.insert(0, KEY_SOURCE_KNXKEYS_EXISTING)
            default_source = KEY_SOURCE_KNXKEYS_EXISTING
        elif manual_configured:
            default_source = KEY_SOURCE_MANUAL
        else:
            default_source = KEY_SOURCE_KNXKEYS_UPLOAD
        return {
            probatio.Required(
                CONF_KNX_SECURE_KEY_SOURCE, default=default_source
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=sources,
                    mode=selector.SelectSelectorMode.LIST,
                    translation_key="secure_key_source",
                )
            ),
            data_entry_flow.Required(
                CONF_KEYRING_FILE, visible=_KEYRING_UPLOAD_VISIBLE
            ): selector.FileSelector(
                config=selector.FileSelectorConfig(accept=".knxkeys")
            ),
            data_entry_flow.Required(
                probatio.Secret(CONF_KNX_KNXKEY_PASSWORD),
                default=self.initial_data.get(CONF_KNX_KNXKEY_PASSWORD),
                visible=_KEYRING_UPLOAD_VISIBLE,
            ): selector.TextSelector(),
        }

    async def async_step_secure_tunnel(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure the IP Secure keys for a tunneling connection."""
        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {}

        if user_input is not None:
            if user_input[CONF_KNX_SECURE_KEY_SOURCE] == KEY_SOURCE_MANUAL:
                self.new_entry_data |= KNXConfigEntryData(
                    device_authentication=user_input[
                        CONF_KNX_SECURE_DEVICE_AUTHENTICATION
                    ],
                    user_id=user_input[CONF_KNX_SECURE_USER_ID],
                    user_password=user_input[CONF_KNX_SECURE_USER_PASSWORD],
                    tunnel_endpoint_ia=None,
                )
                self.new_title = f"Secure Tunneling @ {self.new_entry_data[CONF_HOST]}"
                return self.finish_flow()
            if (
                result := await self._async_handle_keyring_source(
                    user_input[CONF_KNX_SECURE_KEY_SOURCE],
                    user_input,
                    errors,
                    description_placeholders,
                )
            ) is not None:
                return result

        fields: VolDictType = {
            **await self._async_key_source_fields(
                manual_configured=self.initial_data.get(CONF_KNX_SECURE_USER_ID)
                is not None
            ),
            data_entry_flow.Required(
                CONF_KNX_SECURE_USER_ID,
                default=self.initial_data.get(CONF_KNX_SECURE_USER_ID, 2),
                visible=_MANUAL_KEYS_VISIBLE,
            ): probatio.All(
                selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1, max=127, mode=selector.NumberSelectorMode.BOX
                    ),
                ),
                probatio.Coerce(int),
            ),
            data_entry_flow.Required(
                CONF_KNX_SECURE_USER_PASSWORD,
                default=self.initial_data.get(CONF_KNX_SECURE_USER_PASSWORD),
                visible=_MANUAL_KEYS_VISIBLE,
            ): _PASSWORD_SELECTOR,
            data_entry_flow.Required(
                CONF_KNX_SECURE_DEVICE_AUTHENTICATION,
                default=self.initial_data.get(CONF_KNX_SECURE_DEVICE_AUTHENTICATION),
                visible=_MANUAL_KEYS_VISIBLE,
            ): _PASSWORD_SELECTOR,
        }
        data_schema = probatio.Schema(fields)
        if user_input is not None:
            data_schema = self.add_suggested_values_to_schema(data_schema, user_input)
        return self.async_show_form(
            step_id="secure_tunnel",
            data_schema=data_schema,
            errors=errors,
            description_placeholders=description_placeholders,
        )

    async def async_step_secure_routing(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure the IP Secure keys for a routing connection."""
        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {}

        if user_input is not None:
            if user_input[CONF_KNX_SECURE_KEY_SOURCE] == KEY_SOURCE_MANUAL:
                try:
                    key_bytes = bytes.fromhex(user_input[CONF_KNX_ROUTING_BACKBONE_KEY])
                    if len(key_bytes) != 16:
                        raise ValueError  # noqa: TRY301
                except ValueError:
                    errors[CONF_KNX_ROUTING_BACKBONE_KEY] = "invalid_backbone_key"
                if not errors:
                    self.new_entry_data |= KNXConfigEntryData(
                        backbone_key=user_input[CONF_KNX_ROUTING_BACKBONE_KEY],
                        sync_latency_tolerance=user_input[
                            CONF_KNX_ROUTING_SYNC_LATENCY_TOLERANCE
                        ],
                    )
                    return self.finish_flow()
            elif (
                result := await self._async_handle_keyring_source(
                    user_input[CONF_KNX_SECURE_KEY_SOURCE],
                    user_input,
                    errors,
                    description_placeholders,
                )
            ) is not None:
                return result

        fields: VolDictType = {
            **await self._async_key_source_fields(
                manual_configured=self.initial_data.get(CONF_KNX_ROUTING_BACKBONE_KEY)
                is not None
            ),
            data_entry_flow.Required(
                CONF_KNX_ROUTING_BACKBONE_KEY,
                default=self.initial_data.get(CONF_KNX_ROUTING_BACKBONE_KEY),
                visible=_MANUAL_KEYS_VISIBLE,
            ): _PASSWORD_SELECTOR,
            data_entry_flow.Required(
                CONF_KNX_ROUTING_SYNC_LATENCY_TOLERANCE,
                default=self.initial_data.get(CONF_KNX_ROUTING_SYNC_LATENCY_TOLERANCE)
                or 1000,
                visible=_MANUAL_KEYS_VISIBLE,
            ): probatio.All(
                selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=400,
                        max=4000,
                        unit_of_measurement="ms",
                        mode=selector.NumberSelectorMode.BOX,
                    ),
                ),
                probatio.Coerce(int),
            ),
        }
        data_schema = probatio.Schema(fields)
        if user_input is not None:
            data_schema = self.add_suggested_values_to_schema(data_schema, user_input)
        return self.async_show_form(
            step_id="secure_routing",
            data_schema=data_schema,
            errors=errors,
            description_placeholders=description_placeholders,
        )

    async def async_step_secure_knxkeys(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage upload of new KNX Keyring file."""
        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {}

        if user_input is not None:
            if (
                result := await self._async_handle_keyring_source(
                    KEY_SOURCE_KNXKEYS_UPLOAD,
                    user_input,
                    errors,
                    description_placeholders,
                )
            ) is not None:
                return result

        fields = {
            probatio.Required(CONF_KEYRING_FILE): selector.FileSelector(
                config=selector.FileSelectorConfig(accept=".knxkeys")
            ),
            probatio.Required(
                probatio.Secret(CONF_KNX_KNXKEY_PASSWORD),
                default=self.initial_data.get(CONF_KNX_KNXKEY_PASSWORD),
            ): selector.TextSelector(),
        }
        return self.async_show_form(
            step_id="secure_knxkeys",
            data_schema=probatio.Schema(fields),
            errors=errors,
            description_placeholders=description_placeholders,
        )

    async def async_step_knxkeys_tunnel_select(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Select if a specific tunnel should be used from knxkeys file."""
        if user_input is not None:
            selected_tunnel_ia: str | None = None
            _if_user_id: int | None = None
            if user_input[CONF_KNX_TUNNEL_ENDPOINT_IA] == CONF_KNX_AUTOMATIC:
                self.new_entry_data |= KNXConfigEntryData(
                    tunnel_endpoint_ia=None,
                )
            else:
                selected_tunnel_ia = user_input[CONF_KNX_TUNNEL_ENDPOINT_IA]
                self.new_entry_data |= KNXConfigEntryData(
                    tunnel_endpoint_ia=selected_tunnel_ia,
                    user_id=None,
                    user_password=None,
                    device_authentication=None,
                )
                _if_user_id = next(
                    (
                        _if.user_id
                        for _if in self._tunnel_endpoints
                        if str(_if.individual_address) == selected_tunnel_ia
                    ),
                    None,
                )
            _tunnel_identifier = selected_tunnel_ia or self.new_entry_data.get(
                CONF_HOST
            )
            _tunnel_suffix = f" @ {_tunnel_identifier}" if _tunnel_identifier else ""
            self.new_title = (
                f"{'Secure ' if _if_user_id else ''}Tunneling{_tunnel_suffix}"
            )
            return self.finish_flow()

        if TYPE_CHECKING:
            # this step is only called after a keyring was selected
            assert self._keyring

        # Filter for selected tunnel
        if self._selected_tunnel is not None and (
            host_ia := self._selected_tunnel.individual_address
        ):
            self._tunnel_endpoints = self._keyring.get_tunnel_interfaces_by_host(
                host=host_ia
            )
        else:
            self._tunnel_endpoints = self._keyring.interfaces

        tunnel_endpoint_options = [
            selector.SelectOptionDict(
                value=CONF_KNX_AUTOMATIC, label=CONF_KNX_AUTOMATIC.capitalize()
            )
        ]
        tunnel_endpoint_options.extend(
            selector.SelectOptionDict(
                value=str(endpoint.individual_address),
                label=(
                    f"{endpoint.individual_address} "
                    f"{'🔐 ' if endpoint.user_id else ''}"
                    f"(Data Secure GAs: {len(endpoint.group_addresses)})"
                ),
            )
            for endpoint in self._tunnel_endpoints
        )
        default_endpoint = (
            self.initial_data.get(CONF_KNX_TUNNEL_ENDPOINT_IA) or CONF_KNX_AUTOMATIC
        )
        return self.async_show_form(
            step_id="knxkeys_tunnel_select",
            data_schema=probatio.Schema(
                {
                    probatio.Required(
                        CONF_KNX_TUNNEL_ENDPOINT_IA, default=default_endpoint
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=tunnel_endpoint_options,
                            mode=selector.SelectSelectorMode.LIST,
                        )
                    ),
                }
            ),
        )

    async def async_step_routing(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Routing setup."""
        errors: dict = {}
        _individual_address = (
            user_input[CONF_KNX_INDIVIDUAL_ADDRESS]
            if user_input
            else self.initial_data[CONF_KNX_INDIVIDUAL_ADDRESS]
        )
        _multicast_group = (
            user_input[CONF_KNX_MCAST_GRP]
            if user_input
            else self.initial_data[CONF_KNX_MCAST_GRP]
        )
        _multicast_port = (
            user_input[CONF_KNX_MCAST_PORT]
            if user_input
            else self.initial_data[CONF_KNX_MCAST_PORT]
        )

        if user_input is not None:
            try:
                ia_validator(_individual_address)
            except probatio.Invalid:
                errors[CONF_KNX_INDIVIDUAL_ADDRESS] = "invalid_individual_address"
            try:
                ip_v4_validator(_multicast_group, multicast=True)
            except probatio.Invalid:
                errors[CONF_KNX_MCAST_GRP] = "invalid_ip_address"
            if _local := (user_input.get(CONF_KNX_LOCAL_IP) or None):
                try:
                    _local_ip = await xknx_validate_ip(_local)
                    ip_v4_validator(_local_ip, multicast=False)
                except probatio.Invalid, XKNXException:
                    errors[CONF_KNX_LOCAL_IP] = "invalid_ip_address"

            if not errors:
                connection_type = (
                    CONF_KNX_ROUTING_SECURE
                    if user_input[CONF_KNX_ROUTING_SECURE]
                    else CONF_KNX_ROUTING
                )
                self.new_entry_data = KNXConfigEntryData(
                    connection_type=connection_type,
                    individual_address=_individual_address,
                    multicast_group=_multicast_group,
                    multicast_port=_multicast_port,
                    local_ip=_local,
                    device_authentication=None,
                    user_id=None,
                    user_password=None,
                    tunnel_endpoint_ia=None,
                )
                if connection_type == CONF_KNX_ROUTING_SECURE:
                    self.new_title = f"Secure Routing as {_individual_address}"
                    return await self.async_step_secure_routing()
                self.new_title = f"Routing as {_individual_address}"
                return self.finish_flow()

        routers = [router for router in self._found_gateways if router.supports_routing]
        if not routers:
            errors["base"] = "no_router_discovered"
        default_secure_routing_enable = any(
            router for router in routers if router.routing_requires_secure
        )

        fields: VolDictType = {
            probatio.Required(
                CONF_KNX_INDIVIDUAL_ADDRESS, default=_individual_address
            ): _IA_SELECTOR,
            probatio.Required(
                CONF_KNX_ROUTING_SECURE, default=default_secure_routing_enable
            ): selector.BooleanSelector(),
            probatio.Required(
                CONF_KNX_MCAST_GRP, default=_multicast_group
            ): _IP_SELECTOR,
            probatio.Required(
                CONF_KNX_MCAST_PORT, default=_multicast_port
            ): _PORT_SELECTOR,
            probatio.Optional(CONF_KNX_LOCAL_IP): _IP_SELECTOR,
        }
        return self.async_show_form(
            step_id="routing", data_schema=probatio.Schema(fields), errors=errors
        )


class KNXOptionsFlow(OptionsFlowWithReload):
    """Handle KNX options."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize KNX options flow."""
        self.initial_options = dict(config_entry.options)
        self.new_entry_options: KNXConfigEntryOptions = {}

    @callback
    def finish_flow(self) -> ConfigFlowResult:
        """Update the ConfigEntry and finish the flow."""
        return self.async_create_entry(
            title="",
            data=self.initial_options | self.new_entry_options,
        )

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage KNX options."""
        return await self.async_step_communication_settings()

    async def async_step_communication_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage KNX communication settings."""
        if user_input is not None:
            telegram_store_section = user_input[CONF_KNX_TELEGRAM_STORE_SECTION]
            backend = telegram_store_section[CONF_KNX_TELEGRAM_DB_BACKEND]
            self.new_entry_options |= KNXConfigEntryOptions(
                state_updater=user_input[CONF_KNX_STATE_UPDATER],
                rate_limit=user_input[CONF_KNX_RATE_LIMIT],
                telegram_db_load_hours=telegram_store_section[
                    CONF_KNX_TELEGRAM_DB_LOAD_HOURS
                ],
                telegram_db_retention_days=telegram_store_section[
                    CONF_KNX_TELEGRAM_DB_RETENTION_DAYS
                ],
                telegram_db_backend=backend,
            )
            if backend == KNX_TELEGRAM_BACKEND_POSTGRES:
                return await self.async_step_telegram_store_postgres()
            return self.finish_flow()

        data_schema = {
            probatio.Required(
                CONF_KNX_STATE_UPDATER,
                default=self.initial_options.get(
                    CONF_KNX_STATE_UPDATER, CONF_KNX_DEFAULT_STATE_UPDATER
                ),
            ): selector.BooleanSelector(),
            probatio.Required(
                CONF_KNX_RATE_LIMIT,
                default=self.initial_options.get(
                    CONF_KNX_RATE_LIMIT, CONF_KNX_DEFAULT_RATE_LIMIT
                ),
            ): probatio.All(
                selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        max=CONF_MAX_RATE_LIMIT,
                        mode=selector.NumberSelectorMode.BOX,
                    ),
                ),
                probatio.Coerce(int),
            ),
            probatio.Required(CONF_KNX_TELEGRAM_STORE_SECTION): data_entry_flow.section(
                probatio.Schema(
                    {
                        probatio.Required(
                            CONF_KNX_TELEGRAM_DB_LOAD_HOURS,
                            default=self.initial_options.get(
                                CONF_KNX_TELEGRAM_DB_LOAD_HOURS,
                                KNX_TELEGRAM_LOAD_HOURS_DEFAULT,
                            ),
                        ): probatio.All(
                            selector.NumberSelector(
                                selector.NumberSelectorConfig(
                                    min=1,
                                    mode=selector.NumberSelectorMode.BOX,
                                    unit_of_measurement="h",
                                ),
                            ),
                            probatio.Coerce(int),
                        ),
                        probatio.Required(
                            CONF_KNX_TELEGRAM_DB_RETENTION_DAYS,
                            default=self.initial_options.get(
                                CONF_KNX_TELEGRAM_DB_RETENTION_DAYS,
                                KNX_TELEGRAM_DB_RETENTION_DEFAULT,
                            ),
                        ): probatio.All(
                            selector.NumberSelector(
                                selector.NumberSelectorConfig(
                                    min=0,
                                    mode=selector.NumberSelectorMode.BOX,
                                    unit_of_measurement="days",
                                ),
                            ),
                            probatio.Coerce(int),
                        ),
                        probatio.Required(
                            CONF_KNX_TELEGRAM_DB_BACKEND,
                            default=self.initial_options.get(
                                CONF_KNX_TELEGRAM_DB_BACKEND,
                                KNX_TELEGRAM_BACKEND_SQLITE,
                            ),
                        ): selector.SelectSelector(
                            selector.SelectSelectorConfig(
                                options=[
                                    KNX_TELEGRAM_BACKEND_SQLITE,
                                    KNX_TELEGRAM_BACKEND_POSTGRES,
                                ],
                                mode=selector.SelectSelectorMode.DROPDOWN,
                                translation_key="telegram_backend",
                            )
                        ),
                    }
                ),
            ),
        }
        return self.async_show_form(
            step_id="communication_settings",
            data_schema=probatio.Schema(data_schema),
            last_step=False,
        )

    async def async_step_telegram_store_postgres(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect and validate the PostgreSQL telegram store connection."""
        current_dsn = self.initial_options.get(CONF_KNX_TELEGRAM_DB_POSTGRES_DSN, "")
        parsed = _parse_dsn(current_dsn)
        errors: dict[str, str] = {}

        if user_input is not None:
            # Reuse the stored password when the field is left blank.
            params = {
                **user_input,
                CONF_KNX_TELEGRAM_DB_PASSWORD: (
                    user_input.get(CONF_KNX_TELEGRAM_DB_PASSWORD)
                    or parsed.get(CONF_KNX_TELEGRAM_DB_PASSWORD, "")
                ),
            }
            dsn = _build_dsn(params)
            errors = await _async_check_postgres_dsn(dsn)
            if not errors:
                self.new_entry_options |= KNXConfigEntryOptions(
                    telegram_db_postgres_dsn=dsn
                )
                return self.finish_flow()

        data_schema = probatio.Schema(
            {
                probatio.Required(
                    CONF_KNX_TELEGRAM_DB_HOST,
                    default=parsed.get(CONF_KNX_TELEGRAM_DB_HOST, "localhost"),
                ): selector.TextSelector(),
                probatio.Required(
                    CONF_KNX_TELEGRAM_DB_PORT,
                    default=parsed.get(CONF_KNX_TELEGRAM_DB_PORT, 5432),
                ): probatio.All(
                    selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=1,
                            max=65535,
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                    probatio.Coerce(int),
                ),
                probatio.Required(
                    CONF_KNX_TELEGRAM_DB_USER,
                    default=parsed.get(CONF_KNX_TELEGRAM_DB_USER, ""),
                ): selector.TextSelector(),
                probatio.Required(
                    CONF_KNX_TELEGRAM_DB_PASSWORD, default=""
                ): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
                ),
                probatio.Required(
                    CONF_KNX_TELEGRAM_DB_DATABASE,
                    default=parsed.get(CONF_KNX_TELEGRAM_DB_DATABASE, "knx_telegrams"),
                ): selector.TextSelector(),
                probatio.Required(
                    CONF_KNX_TELEGRAM_DB_TLS,
                    default=parsed.get(CONF_KNX_TELEGRAM_DB_TLS, False),
                ): selector.BooleanSelector(),
            }
        )
        if user_input is not None:
            data_schema = self.add_suggested_values_to_schema(data_schema, user_input)
        return self.async_show_form(
            step_id="telegram_store_postgres",
            data_schema=data_schema,
            errors=errors,
            last_step=True,
        )


async def _async_check_postgres_dsn(dsn: str) -> dict[str, str]:
    """Validate a PostgreSQL DSN, returning form errors on failure."""
    connection_errors = {
        ConnectionErrorKind.AUTH: "invalid_auth",
        ConnectionErrorKind.HOST_UNREACHABLE: "host_unreachable",
        ConnectionErrorKind.DATABASE_MISSING: "database_missing",
        ConnectionErrorKind.PERMISSION: "permission",
        ConnectionErrorKind.TIMEOUT: "timeout",
        ConnectionErrorKind.MISSING_DEPENDENCY: "missing_dependency",
    }
    try:
        async with asyncio.timeout(DSN_CHECK_TIMEOUT):
            check_result = await PostgresStore.check_config(dsn)
    except TimeoutError:
        return {"base": "timeout"}
    except ValueError:
        return {"base": "cannot_connect"}
    if not check_result.ok:
        return {"base": connection_errors.get(check_result.kind, "cannot_connect")}
    return {}


def _build_dsn(params: dict[str, Any]) -> str:
    """Build a PostgreSQL DSN from form params."""
    quoted_user = quote(params.get(CONF_KNX_TELEGRAM_DB_USER, ""), safe="")
    quoted_password = quote(params.get(CONF_KNX_TELEGRAM_DB_PASSWORD, ""), safe="")
    host = params.get(CONF_KNX_TELEGRAM_DB_HOST, "localhost")
    if ":" in host and not host.startswith("["):
        # IPv6 literals must be bracketed in the URL netloc
        host = f"[{host}]"
    port = int(params.get(CONF_KNX_TELEGRAM_DB_PORT, 5432))
    quoted_database = quote(
        params.get(CONF_KNX_TELEGRAM_DB_DATABASE, "knx_telegrams"), safe=""
    )
    tls = params.get(CONF_KNX_TELEGRAM_DB_TLS, False)

    netloc = f"{quoted_user}:{quoted_password}@{host}:{port}"
    query = "sslmode=require" if tls else ""
    return urlunparse(("postgresql", netloc, f"/{quoted_database}", "", query, ""))


def _parse_dsn(dsn: str) -> dict[str, Any]:
    """Parse a PostgreSQL DSN into form params."""
    if not dsn:
        return {}
    try:
        url = urlparse(dsn)
        return {
            CONF_KNX_TELEGRAM_DB_USER: unquote(url.username or ""),
            CONF_KNX_TELEGRAM_DB_PASSWORD: unquote(url.password or ""),
            CONF_KNX_TELEGRAM_DB_HOST: url.hostname or "localhost",
            CONF_KNX_TELEGRAM_DB_PORT: url.port or 5432,
            CONF_KNX_TELEGRAM_DB_DATABASE: unquote(url.path.lstrip("/")),
            CONF_KNX_TELEGRAM_DB_TLS: "sslmode=require" in url.query,
        }
    except ValueError, AttributeError:
        return {}
