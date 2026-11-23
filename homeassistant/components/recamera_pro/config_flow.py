"""Config flow for reCamera Pro."""

import asyncio
from collections.abc import Mapping
import contextlib
from ipaddress import ip_address, ip_network
import logging
from typing import Any, override

import probatio
from recamera_protocol import (
    DetectedClass,
    RecameraAuthenticationError,
    RecameraConnectionError,
    RecameraError,
    RecameraProbeResult,
    RecameraProtocolError,
    async_probe_device,
    normalize_mac_address,
    normalize_serial_number,
)
from zeroconf._exceptions import NotRunningException
from zeroconf.asyncio import AsyncServiceInfo

from homeassistant import data_entry_flow
from homeassistant.components import zeroconf as ha_zeroconf
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import discovery_flow, selector
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
from homeassistant.helpers.storage import Store

from .const import (
    CONF_AUDIO_CONFIDENCE,
    CONF_AUDIO_COOLDOWN,
    CONF_CLASS_STALE_SECONDS,
    CONF_DEVICE_ID,
    CONF_DISCOVERY_CANDIDATES,
    CONF_DISCOVERY_ID,
    CONF_HW_VERSION,
    CONF_MAC_ADDRESS,
    CONF_MODEL,
    CONF_SERIAL_NUMBER,
    CONF_SW_VERSION,
    CONF_TRACKED_CLASSES,
    CONF_VISUAL_CONFIDENCE,
    CONF_VISUAL_CONFIRM,
    CONF_VISUAL_COOLDOWN,
    CONFIG_ENTRY_VERSION,
    DEFAULT_AUDIO_CONFIDENCE,
    DEFAULT_AUDIO_COOLDOWN,
    DEFAULT_CLASS_STALE_SECONDS,
    DEFAULT_TRACKED_CLASSES,
    DEFAULT_VISUAL_CONFIDENCE,
    DEFAULT_VISUAL_CONFIRM,
    DEFAULT_VISUAL_COOLDOWN,
    DOMAIN,
    SERVICE_TYPE,
    STORAGE_VERSION,
)
from .discovery_candidates import merge_discovery_candidate
from .identity import device_title, probe_identity_mismatch

_LOGGER = logging.getLogger(__name__)
_DISCOVERY_PROBE_TOTAL_SECONDS = 15.0
_DISCOVERY_PROBE_PER_HOST_SECONDS = 8.0
_DISCOVERY_REFRESH_INTERVAL = 2.0
_DISCOVERY_RESOLVE_TIMEOUT = 3.0


def _text(value: Any) -> str:
    """Normalize a Zeroconf TXT value."""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace").strip()
    return str(value or "").strip()


_IGNORED_DISCOVERY_NETWORKS = (
    ip_network("127.0.0.0/8"),
    ip_network("169.254.0.0/16"),
    ip_network("172.17.0.0/16"),
    ip_network("172.30.32.0/23"),
    ip_network("::1/128"),
    ip_network("fe80::/10"),
)


def _is_ignored_discovery_host(candidate: str) -> bool:
    """Return True for loopback, link-local, and container bridge IPs."""
    try:
        addr = ip_address(candidate)
    except ValueError:
        return False
    return any(addr in net for net in _IGNORED_DISCOVERY_NETWORKS)


def _discovery_hosts(host: object, addresses: object) -> list[str]:
    """Return unique, non-empty native Zeroconf addresses with routable hosts first."""
    candidates = [host]
    if isinstance(addresses, (list, tuple, set)):
        candidates.extend(addresses)
    all_hosts: list[str] = []
    for candidate in candidates:
        normalized = str(candidate or "").strip().lower()
        if normalized and normalized not in all_hosts:
            all_hosts.append(normalized)
    filtered = [h for h in all_hosts if not _is_ignored_discovery_host(h)]
    return filtered or all_hosts


async def _prioritize_reachable_hosts(hosts: list[str]) -> list[str]:
    """Move the first TCP-443 reachable host to index 0."""
    if len(hosts) <= 1:
        return hosts
    for index, host in enumerate(hosts):
        try:
            async with asyncio.timeout(0.3):
                _, writer = await asyncio.open_connection(host, 443)
                writer.close()
                await writer.wait_closed()
        except OSError, TimeoutError:
            continue
        if index == 0:
            return hosts
        return [host, *hosts[:index], *hosts[index + 1 :]]
    return hosts


async def _any_host_reachable(hosts: list[str]) -> bool:
    """Return whether any candidate host responds on HTTPS."""
    for host in hosts:
        try:
            async with asyncio.timeout(0.3):
                _, writer = await asyncio.open_connection(host, 443)
                writer.close()
                await writer.wait_closed()
                return True
        except OSError, TimeoutError:
            continue
    return False


async def _async_probe_device_with_hass(
    hass: object,
    host: str,
    username: str,
    password: str,
) -> RecameraProbeResult:
    """Probe one candidate host using an isolated short-lived session."""
    del hass
    return await async_probe_device(
        host,
        username,
        password,
    )


async def _options_catalog(
    config_entry: ConfigEntry, hass: HomeAssistant
) -> dict[str, DetectedClass]:
    """Load options without requiring a live coordinator."""
    coordinator = getattr(config_entry, "runtime_data", None)
    if coordinator is not None and coordinator.data is not None:
        return dict(coordinator.data.class_catalog)

    loaded = await Store[dict[str, Any]](
        hass, STORAGE_VERSION, f"{DOMAIN}.{config_entry.entry_id}"
    ).async_load()
    stored: dict[str, Any] = loaded if isinstance(loaded, dict) else {}
    catalog: dict[str, DetectedClass] = {}
    for item in stored.get("class_catalog") or []:
        if not isinstance(item, dict):
            continue
        detected_class = DetectedClass.from_dict(item)
        if detected_class is not None:
            catalog[detected_class.key] = detected_class
    for item in stored.get("discovered_classes") or []:
        if not isinstance(item, list) or len(item) != 2:
            continue
        detected_class = DetectedClass.from_dict(
            {
                "source_id": item[0],
                "class_name": item[1],
                "task_type": "detection",
            }
        )
        if detected_class is not None:
            catalog.setdefault(detected_class.key, detected_class)
    return catalog


async def _async_resolve_zeroconf_service(
    hass: Any,
    service_type: str,
    service_name: str,
) -> tuple[list[str], int | None, str, dict[str, Any]] | None:
    """Resolve current A/AAAA addresses for one Zeroconf service instance."""
    shared = await ha_zeroconf.async_get_async_instance(hass)
    if shared.zeroconf.done:
        return None
    zeroconf_instance = shared.zeroconf
    async with asyncio.timeout(10):
        service_info = AsyncServiceInfo(service_type, service_name)
        for _ in range(2):
            if service_info.server:
                stale_records = []
                for record_type in (1, 28):
                    stale_records.extend(
                        zeroconf_instance.cache.async_all_by_details(
                            service_info.server,
                            record_type,
                            1,
                        )
                    )
                if stale_records:
                    zeroconf_instance.cache.async_remove_records(stale_records)
            await service_info.async_request(
                zeroconf_instance,
                _DISCOVERY_RESOLVE_TIMEOUT * 1000,
            )
        addresses: list[str] = []
        for value in service_info.parsed_addresses():
            try:
                address = ip_address(value)
            except ValueError:
                continue
            if address.is_unspecified or address.is_link_local:
                continue
            if str(address) not in addresses:
                addresses.append(str(address))
        return (
            addresses,
            service_info.port,
            str(service_info.server or ""),
            dict(service_info.decoded_properties),
        )


class RecameraProOptionsFlow(OptionsFlowWithReload):
    """Grouped runtime detection settings."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the settings categories supported by reCamera Pro."""
        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "vision",
                "sound",
                "classes",
            ],
        )

    async def async_step_vision(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure YOLO runtime parameters."""
        options = self.config_entry.options
        if user_input is not None:
            return self.async_create_entry(data={**options, **user_input})
        return self.async_show_form(
            step_id="vision",
            data_schema=probatio.Schema(
                {
                    probatio.Required(
                        CONF_VISUAL_CONFIDENCE,
                        default=float(
                            options.get(
                                CONF_VISUAL_CONFIDENCE,
                                DEFAULT_VISUAL_CONFIDENCE,
                            )
                        ),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0,
                            max=1,
                            step=0.01,
                            mode=selector.NumberSelectorMode.SLIDER,
                        )
                    ),
                    probatio.Required(
                        CONF_VISUAL_CONFIRM,
                        default=float(
                            options.get(
                                CONF_VISUAL_CONFIRM,
                                DEFAULT_VISUAL_CONFIRM,
                            )
                        ),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0,
                            max=30,
                            step=0.1,
                            unit_of_measurement="s",
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                    probatio.Required(
                        CONF_CLASS_STALE_SECONDS,
                        default=float(
                            options.get(
                                CONF_CLASS_STALE_SECONDS,
                                DEFAULT_CLASS_STALE_SECONDS,
                            )
                        ),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=1,
                            max=60,
                            step=1,
                            unit_of_measurement="s",
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                    probatio.Required(
                        CONF_VISUAL_COOLDOWN,
                        default=float(
                            options.get(
                                CONF_VISUAL_COOLDOWN,
                                DEFAULT_VISUAL_COOLDOWN,
                            )
                        ),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0,
                            max=60,
                            step=1,
                            unit_of_measurement="s",
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                }
            ),
        )

    async def async_step_sound(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure sound recognition parameters."""
        options = self.config_entry.options
        if user_input is not None:
            return self.async_create_entry(data={**options, **user_input})
        return self.async_show_form(
            step_id="sound",
            data_schema=probatio.Schema(
                {
                    probatio.Required(
                        CONF_AUDIO_CONFIDENCE,
                        default=float(
                            options.get(
                                CONF_AUDIO_CONFIDENCE,
                                DEFAULT_AUDIO_CONFIDENCE,
                            )
                        ),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0,
                            max=1,
                            step=0.01,
                            mode=selector.NumberSelectorMode.SLIDER,
                        )
                    ),
                    probatio.Required(
                        CONF_AUDIO_COOLDOWN,
                        default=float(
                            options.get(
                                CONF_AUDIO_COOLDOWN,
                                DEFAULT_AUDIO_COOLDOWN,
                            )
                        ),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0,
                            max=60,
                            step=1,
                            unit_of_measurement="s",
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                }
            ),
        )

    async def async_step_classes(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select YOLO classes that expose binary sensors."""
        catalog = await _options_catalog(self.config_entry, self.hass)
        class_options = [
            selector.SelectOptionDict(
                value=item.key,
                label=item.label,
            )
            for item in sorted(
                (item for item in catalog.values() if item.source_id == "builtin"),
                key=lambda item: item.class_name,
            )
        ]
        options = self.config_entry.options
        if user_input is not None:
            return self.async_create_entry(data={**options, **user_input})
        return self.async_show_form(
            step_id="classes",
            data_schema=probatio.Schema(
                {
                    probatio.Optional(
                        CONF_TRACKED_CLASSES,
                        default=list(
                            options.get(
                                CONF_TRACKED_CLASSES,
                                DEFAULT_TRACKED_CLASSES,
                            )
                        ),
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=class_options,
                            multiple=True,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
            description_placeholders={"class_count": str(len(class_options))},
        )


class RecameraProConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle reCamera Pro configuration."""

    VERSION = CONFIG_ENTRY_VERSION

    def __init__(self) -> None:
        """Initialize a config flow."""
        self._discovery_name: str | None = None
        self._discovery_id: str | None = None
        self._discovery_serial: str | None = None
        self._discovery_mac: str | None = None
        self._discovery_host: str | None = None
        self._discovery_hosts: list[str] = []
        self._discovery_service_type: str | None = None
        self._discovery_service_name: str | None = None
        self._discovery_properties: dict[str, str] = {}
        self._discovery_refresh_task: asyncio.Task[None] | None = None
        self._discovery_refresh_candidate: list[str] | None = None
        self._discovery_form_shown = False

    @staticmethod
    @callback
    @override
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> RecameraProOptionsFlow:
        """Return the options flow."""
        return RecameraProOptionsFlow()

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add a camera manually."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = str(user_input[CONF_HOST]).strip().lower()
            self._async_abort_entries_match({CONF_HOST: host})
            try:
                probe = await _async_probe_device_with_hass(
                    getattr(self, "hass", None),
                    host,
                    str(user_input[CONF_USERNAME]).strip() or "admin",
                    str(user_input[CONF_PASSWORD]),
                )
            except RecameraAuthenticationError:
                errors["base"] = "invalid_auth"
            except (
                RecameraConnectionError,
                RecameraProtocolError,
                RecameraError,
            ):
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected reCamera Pro setup error")
                errors["base"] = "unknown"
            else:
                unique_id = self._stable_identity(probe)
                if unique_id is None:
                    errors["base"] = "identity_unavailable"
                else:
                    await self.async_set_unique_id(unique_id)
                    self._abort_if_unique_id_configured(updates={CONF_HOST: host})
                    return self.async_create_entry(
                        title=self._title(probe, host=host),
                        data=self._entry_data(
                            host=host,
                            username=str(user_input[CONF_USERNAME]).strip() or "admin",
                            password=str(user_input[CONF_PASSWORD]),
                            unique_id=unique_id,
                            probe=probe,
                        ),
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_HOST): str,
                    probatio.Required(CONF_USERNAME, default="admin"): str,
                    probatio.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    @override
    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle Zeroconf discovery."""
        if discovery_info.type != SERVICE_TYPE:
            return self.async_abort(reason="unsupported_discovery")

        properties = {
            str(key): _text(value) for key, value in discovery_info.properties.items()
        }
        discovery_id = properties.get("id") or None
        discovery_mac = normalize_mac_address(properties.get("mac"))
        self._discovery_serial = normalize_serial_number(properties.get("serial"))
        self._discovery_mac = discovery_mac
        hosts = _discovery_hosts(
            discovery_info.host,
            getattr(discovery_info, "ip_addresses", None),
        )
        service_suffix = f".{discovery_info.type}"
        self._discovery_name = discovery_info.name.removesuffix(service_suffix)
        self._discovery_id = discovery_id
        self._discovery_service_type = discovery_info.type
        self._discovery_service_name = discovery_info.name
        self._discovery_properties = dict(properties)
        canonical_discovery_id = self._canonical_discovery_identity()

        existing_entry = next(
            (
                entry
                for entry in self._async_current_entries()
                if (
                    canonical_discovery_id
                    and (
                        entry.unique_id == canonical_discovery_id
                        or entry.data.get(CONF_DEVICE_ID) == canonical_discovery_id
                    )
                )
                or (
                    discovery_id
                    and (
                        entry.unique_id == discovery_id
                        or entry.data.get(CONF_DISCOVERY_ID) == discovery_id
                    )
                )
                or (
                    discovery_mac
                    and normalize_mac_address(entry.data.get(CONF_MAC_ADDRESS))
                    == discovery_mac
                )
            ),
            None,
        )
        if existing_entry is None:
            other_hosts = {
                str(entry.data.get(CONF_HOST) or "").strip().lower()
                for entry in self._async_current_entries()
            }
            unclaimed = [h for h in hosts if h not in other_hosts]
            if unclaimed:
                hosts = unclaimed
        hosts = await _prioritize_reachable_hosts(hosts)
        host = hosts[0]
        self._discovery_host = host
        self._discovery_hosts = hosts
        if existing_entry is not None:
            return await self._async_validate_discovery_update(
                existing_entry,
                hosts,
                discovery_id,
            )

        if canonical_discovery_id:
            pending = self._pending_discovery_flow(canonical_discovery_id)
            if pending is not None:
                return self.async_abort(reason="already_in_progress")

        if canonical_discovery_id:
            await self.async_set_unique_id(canonical_discovery_id)
            self._abort_if_unique_id_configured(updates={CONF_HOST: host})
        else:
            self._async_abort_entries_match({CONF_HOST: host})

        self.context["title_placeholders"] = {"name": self._discovery_name}
        _LOGGER.info(
            "reCamera discovery flow active: %s -> %s",
            discovery_info.name,
            hosts,
        )
        self._start_discovery_refresh(
            discovery_info.type,
            discovery_info.name,
        )
        return await self.async_step_zeroconf_confirm()

    def _pending_discovery_flow(self, unique_id: str) -> ConfigFlowResult | None:
        """Return the pending discovery for one physical device."""
        for flow in self.hass.config_entries.flow.async_progress_by_handler(DOMAIN):
            context = flow.get("context", {})
            if (
                context.get("source") == "zeroconf"
                and context.get("unique_id") == unique_id
            ):
                return flow
        return None

    def _start_discovery_refresh(
        self,
        service_type: str,
        service_name: str,
    ) -> None:
        """Refresh one pending service without scanning the network."""
        create_task = getattr(
            self.hass,
            "async_create_background_task",
            None,
        )
        if create_task is None:
            return
        if (
            self._discovery_refresh_task is not None
            and not self._discovery_refresh_task.done()
        ):
            return
        self._cancel_discovery_refresh()
        self._discovery_refresh_task = create_task(
            self._async_refresh_discovery(
                service_type,
                service_name,
            ),
            name=f"reCamera discovery refresh {service_name}",
        )
        _LOGGER.debug(
            "Started reCamera discovery refresh for %s",
            service_name,
        )

    def _cancel_discovery_refresh(self) -> None:
        """Stop a pending discovery refresh after user or manager action."""
        task = self._discovery_refresh_task
        self._discovery_refresh_task = None
        if task is not None and not task.done():
            task.cancel()

    async def _async_refresh_discovery(
        self,
        service_type: str,
        service_name: str,
    ) -> None:
        """Resolve the current service instance when cached A records are stale."""
        empty_cycles = 0
        try:
            while True:
                try:
                    self.hass.config_entries.flow.async_get(self.flow_id)
                except data_entry_flow.UnknownFlow:
                    _LOGGER.info(
                        "reCamera discovery flow removed: %s",
                        self.flow_id,
                    )
                    return
                except IndexError:
                    pass
                addresses: list[str] = []
                resolved_port: int | None = 80
                resolved_server = "reCamera-Pro.local."
                resolved_properties = dict(getattr(self, "_discovery_properties", {}))
                try:
                    resolved = await _async_resolve_zeroconf_service(
                        self.hass,
                        service_type,
                        service_name,
                    )
                except NotRunningException:
                    await asyncio.sleep(_DISCOVERY_REFRESH_INTERVAL)
                    continue
                except Exception:
                    _LOGGER.debug(
                        "Unable to refresh reCamera discovery %s",
                        service_name,
                        exc_info=True,
                    )
                    await asyncio.sleep(_DISCOVERY_REFRESH_INTERVAL)
                    continue
                if resolved is None:
                    await asyncio.sleep(_DISCOVERY_REFRESH_INTERVAL)
                    continue
                addresses, resolved_port, resolved_server, decoded_props = resolved
                resolved_properties = {**resolved_properties, **decoded_props}
                if not addresses:
                    self._discovery_refresh_candidate = None
                    previous_hosts = list(self._discovery_hosts)
                    if not self._discovery_form_shown and not await _any_host_reachable(
                        previous_hosts
                    ):
                        empty_cycles += 1
                        if empty_cycles >= 2:
                            _LOGGER.info(
                                "Aborting offline reCamera discovery %s",
                                service_name,
                            )
                            with contextlib.suppress(data_entry_flow.UnknownFlow):
                                self.hass.config_entries.flow.async_abort(self.flow_id)
                            return
                    else:
                        empty_cycles = 0
                    await asyncio.sleep(_DISCOVERY_REFRESH_INTERVAL)
                    continue
                empty_cycles = 0

                _LOGGER.debug(
                    "Resolved reCamera discovery %s -> %s",
                    service_name,
                    addresses,
                )

                previous = list(self._discovery_hosts)
                if previous == addresses:
                    self._discovery_refresh_candidate = None
                    await asyncio.sleep(_DISCOVERY_REFRESH_INTERVAL)
                    continue

                if self._discovery_form_shown:
                    self._discovery_host = addresses[0]
                    self._discovery_hosts = list(addresses)
                    self._discovery_refresh_candidate = None
                    _LOGGER.info(
                        "Updated active reCamera form candidates %s -> %s",
                        previous,
                        addresses,
                    )
                    await asyncio.sleep(_DISCOVERY_REFRESH_INTERVAL)
                    continue

                if previous and previous[0] == addresses[0]:
                    self._discovery_hosts = list(addresses)
                    self._discovery_refresh_candidate = None
                    await asyncio.sleep(_DISCOVERY_REFRESH_INTERVAL)
                    continue

                if self._discovery_refresh_candidate != addresses:
                    previous_alive = await _any_host_reachable(previous[:1])
                    if previous_alive or not await _any_host_reachable(addresses[:1]):
                        self._discovery_refresh_candidate = list(addresses)
                        _LOGGER.debug(
                            "reCamera discovery candidate %s -> %s",
                            previous,
                            addresses,
                        )
                        await asyncio.sleep(_DISCOVERY_REFRESH_INTERVAL)
                        continue

                _LOGGER.info(
                    "reCamera discovery refreshed %s -> %s",
                    previous,
                    addresses,
                )
                refreshed = ZeroconfServiceInfo(
                    ip_address=ip_address(addresses[0]),
                    ip_addresses=[ip_address(value) for value in addresses],
                    port=resolved_port,
                    hostname=resolved_server,
                    type=service_type,
                    name=service_name,
                    properties=resolved_properties,
                )
                discovery_key = self.context.get("discovery_key")
                try:
                    self.hass.config_entries.flow.async_abort(self.flow_id)
                except data_entry_flow.UnknownFlow:
                    return
                await asyncio.sleep(0)
                discovery_flow.async_create_flow(
                    self.hass,
                    DOMAIN,
                    context={"source": "zeroconf"},
                    data=refreshed,
                    discovery_key=discovery_key,
                )
                return
        finally:
            _LOGGER.info(
                "reCamera discovery refresh stopped: %s",
                service_name,
            )

    async def _async_probe_existing_discovery_hosts(
        self,
        entry: ConfigEntry,
        hosts: list[str],
    ) -> tuple[str | None, RecameraProbeResult | None, str | None]:
        """Probe all advertised addresses within one bounded total budget."""
        deadline = asyncio.get_running_loop().time() + _DISCOVERY_PROBE_TOTAL_SECONDS
        saw_auth_error = False
        saw_identity_mismatch = False
        username = str(entry.data.get(CONF_USERNAME, "admin"))
        password = str(entry.data.get(CONF_PASSWORD, ""))
        for candidate in hosts:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                break
            try:
                async with asyncio.timeout(
                    min(_DISCOVERY_PROBE_PER_HOST_SECONDS, remaining)
                ):
                    probe = await _async_probe_device_with_hass(
                        getattr(self, "hass", None),
                        candidate,
                        username,
                        password,
                    )
            except RecameraAuthenticationError:
                saw_auth_error = True
                continue
            except RecameraError, TimeoutError:
                continue
            except Exception:
                _LOGGER.exception(
                    "Unexpected reCamera discovery candidate error for %s",
                    candidate,
                )
                continue
            if self._identity_mismatch(entry, probe):
                saw_identity_mismatch = True
                continue
            return candidate, probe, None
        if saw_auth_error:
            return None, None, "invalid_auth"
        if saw_identity_mismatch:
            return None, None, "identity_mismatch"
        return None, None, "cannot_connect"

    async def _async_probe_new_discovery_hosts(
        self,
        hosts: list[str],
        username: str,
        password: str,
    ) -> tuple[str | None, RecameraProbeResult | None, str | None]:
        """Probe a new device's advertised addresses with one total budget."""
        deadline = asyncio.get_running_loop().time() + _DISCOVERY_PROBE_TOTAL_SECONDS
        saw_auth_error = False
        saw_identity_mismatch = False
        for candidate in hosts:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                break
            try:
                async with asyncio.timeout(
                    min(_DISCOVERY_PROBE_PER_HOST_SECONDS, remaining)
                ):
                    probe = await _async_probe_device_with_hass(
                        getattr(self, "hass", None),
                        candidate,
                        username,
                        password,
                    )
            except RecameraAuthenticationError:
                saw_auth_error = True
                continue
            except RecameraError, TimeoutError:
                continue
            except Exception:
                _LOGGER.exception(
                    "Unexpected reCamera new discovery error for %s",
                    candidate,
                )
                continue
            if self._discovery_identity_mismatch(probe):
                saw_identity_mismatch = True
                continue
            return candidate, probe, None
        if saw_auth_error:
            return None, None, "invalid_auth"
        if saw_identity_mismatch:
            return None, None, "identity_mismatch"
        return None, None, "cannot_connect"

    async def _async_validate_discovery_update(
        self,
        entry: ConfigEntry,
        hosts: list[str] | str,
        discovery_id: str | None,
    ) -> ConfigFlowResult:
        """Authenticate a discovery candidate before changing a host."""
        candidates = [hosts] if isinstance(hosts, str) else list(hosts)
        (
            selected_host,
            probe,
            failure,
        ) = await self._async_probe_existing_discovery_hosts(
            entry,
            candidates,
        )
        if failure is not None or selected_host is None or probe is None:
            return self.async_abort(reason=failure or "cannot_connect")
        host = selected_host

        updates = {
            CONF_HOST: host,
            CONF_DISCOVERY_CANDIDATES: merge_discovery_candidate(
                dict(entry.data),
                host,
            ),
            CONF_MAC_ADDRESS: (
                probe.info.mac_address or entry.data.get(CONF_MAC_ADDRESS)
            ),
            CONF_SERIAL_NUMBER: (
                probe.info.serial_number
                or normalize_serial_number(entry.data.get(CONF_SERIAL_NUMBER))
            ),
            CONF_MODEL: (probe.info.base_plate_model or entry.data.get(CONF_MODEL)),
            CONF_HW_VERSION: (
                probe.info.hardware_version
                or probe.info.sensor_model
                or entry.data.get(CONF_HW_VERSION)
            ),
            CONF_SW_VERSION: (
                probe.info.firmware_version or entry.data.get(CONF_SW_VERSION)
            ),
        }
        if discovery_id:
            updates[CONF_DISCOVERY_ID] = discovery_id
        current_host = str(entry.data.get(CONF_HOST) or "").strip().lower()
        connection_changed = host != current_host
        coordinator = getattr(entry, "runtime_data", None)
        if (
            connection_changed
            and coordinator is not None
            and coordinator.last_update_success
        ):
            old_host_healthy = False
            if current_host:
                try:
                    current_probe = await _async_probe_device_with_hass(
                        getattr(self, "hass", None),
                        current_host,
                        str(entry.data.get(CONF_USERNAME, "admin")),
                        str(entry.data.get(CONF_PASSWORD, "")),
                    )
                except RecameraError:
                    pass
                except Exception:
                    _LOGGER.exception("Unexpected reCamera current-host check error")
                else:
                    old_host_healthy = not self._identity_mismatch(
                        entry,
                        current_probe,
                    )
            if old_host_healthy:
                # Alternate mDNS interfaces must not make a health-checked
                # connection flap. The new host was authenticated above and
                # will be reconsidered if the device announces it again.
                updates.pop(CONF_HOST, None)
                connection_changed = False
        data = {**entry.data, **updates}
        if connection_changed:
            return self.async_update_reload_and_abort(
                entry,
                data=data,
                reason="already_configured",
            )
        self.hass.config_entries.async_update_entry(
            entry,
            data=data,
        )
        return self.async_abort(reason="already_configured")

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Authenticate a discovered camera."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._discovery_form_shown = True
            host = str(user_input[CONF_HOST]).strip().lower()
            username = str(user_input[CONF_USERNAME]).strip() or "admin"
            password = str(user_input[CONF_PASSWORD])
            selected_host, probe, failure = await self._async_probe_new_discovery_hosts(
                _discovery_hosts(host, self._discovery_hosts),
                username,
                password,
            )
            if failure is not None or selected_host is None or probe is None:
                errors["base"] = failure or "cannot_connect"
            else:
                host = selected_host
                unique_id = self._stable_identity(probe)
                if unique_id is None:
                    errors["base"] = "identity_unavailable"
                else:
                    await self.async_set_unique_id(unique_id)
                    self._abort_if_unique_id_configured(updates={CONF_HOST: host})
                    data = self._entry_data(
                        host=host,
                        username=username,
                        password=password,
                        unique_id=unique_id,
                        probe=probe,
                    )
                    if self._discovery_id:
                        data[CONF_DISCOVERY_ID] = self._discovery_id
                    self._cancel_discovery_refresh()
                    return self.async_create_entry(
                        title=(self._discovery_name or self._title(probe, host=host)),
                        data=data,
                    )

        if (
            self._discovery_service_type is not None
            and self._discovery_service_name is not None
        ):
            self._start_discovery_refresh(
                self._discovery_service_type,
                self._discovery_service_name,
            )
        return self.async_show_form(
            step_id="zeroconf_confirm",
            data_schema=probatio.Schema(
                {
                    probatio.Required(
                        CONF_HOST, default=self._discovery_host or ""
                    ): str,
                    probatio.Required(CONF_USERNAME, default="admin"): str,
                    probatio.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
            description_placeholders={
                "name": self._discovery_name or "reCamera Pro",
            },
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start reauthentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Update rejected credentials."""
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            password = str(user_input[CONF_PASSWORD])
            try:
                probe = await _async_probe_device_with_hass(
                    getattr(self, "hass", None),
                    entry.data[CONF_HOST],
                    str(user_input[CONF_USERNAME]).strip() or "admin",
                    password,
                )
            except RecameraAuthenticationError:
                errors["base"] = "invalid_auth"
            except RecameraError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected reCamera Pro reauthentication error")
                errors["base"] = "unknown"
            else:
                if self._identity_mismatch(entry, probe):
                    errors["base"] = "identity_mismatch"
                else:
                    return self.async_update_reload_and_abort(
                        entry,
                        data=self._updated_entry_data(
                            entry,
                            probe,
                            username=str(user_input[CONF_USERNAME]).strip() or "admin",
                            password=password,
                        ),
                        reason="reauth_successful",
                    )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=probatio.Schema(
                {
                    probatio.Required(
                        CONF_USERNAME,
                        default=entry.data.get(CONF_USERNAME, "admin"),
                    ): str,
                    probatio.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Update connection settings."""
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()
        if user_input is not None:
            host = str(user_input[CONF_HOST]).strip().lower()
            password = str(user_input[CONF_PASSWORD]) or str(
                entry.data.get(CONF_PASSWORD) or ""
            )
            try:
                probe = await _async_probe_device_with_hass(
                    getattr(self, "hass", None),
                    host,
                    str(user_input[CONF_USERNAME]).strip() or "admin",
                    password,
                )
            except RecameraAuthenticationError:
                errors["base"] = "invalid_auth"
            except RecameraError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected reCamera Pro reconfiguration error")
                errors["base"] = "unknown"
            else:
                if self._identity_mismatch(entry, probe):
                    errors["base"] = "identity_mismatch"
                else:
                    return self.async_update_reload_and_abort(
                        entry,
                        data={
                            **self._updated_entry_data(
                                entry,
                                probe,
                                username=str(user_input[CONF_USERNAME]).strip()
                                or "admin",
                                password=password,
                            ),
                            CONF_HOST: host,
                        },
                        reason="reconfigure_successful",
                    )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=probatio.Schema(
                {
                    probatio.Required(
                        CONF_HOST,
                        default=entry.data.get(CONF_HOST, ""),
                    ): str,
                    probatio.Required(
                        CONF_USERNAME,
                        default=entry.data.get(CONF_USERNAME, "admin"),
                    ): str,
                    probatio.Optional(CONF_PASSWORD, default=""): str,
                }
            ),
            errors=errors,
        )

    @staticmethod
    def _entry_data(
        *,
        host: str,
        username: str,
        password: str,
        unique_id: str,
        probe: RecameraProbeResult,
    ) -> dict[str, Any]:
        """Build normalized config entry data."""
        return {
            CONF_HOST: host,
            CONF_USERNAME: username,
            CONF_PASSWORD: password,
            CONF_DEVICE_ID: unique_id,
            CONF_SERIAL_NUMBER: probe.info.serial_number,
            CONF_MAC_ADDRESS: probe.info.mac_address,
            CONF_MODEL: (probe.info.base_plate_model or "reCamera Pro"),
            CONF_HW_VERSION: (probe.info.hardware_version or probe.info.sensor_model),
            CONF_SW_VERSION: probe.info.firmware_version,
        }

    @staticmethod
    def _updated_entry_data(
        entry: ConfigEntry,
        probe: RecameraProbeResult,
        *,
        username: str,
        password: str,
    ) -> dict[str, Any]:
        """Return refreshed entry data while retaining stable identity."""
        return {
            **entry.data,
            CONF_USERNAME: username,
            CONF_PASSWORD: password,
            CONF_SERIAL_NUMBER: (
                probe.info.serial_number
                or normalize_serial_number(entry.data.get(CONF_SERIAL_NUMBER))
            ),
            CONF_MAC_ADDRESS: (
                probe.info.mac_address or entry.data.get(CONF_MAC_ADDRESS)
            ),
            CONF_MODEL: (probe.info.base_plate_model or entry.data.get(CONF_MODEL)),
            CONF_HW_VERSION: (
                probe.info.hardware_version
                or probe.info.sensor_model
                or entry.data.get(CONF_HW_VERSION)
            ),
            CONF_SW_VERSION: (
                probe.info.firmware_version or entry.data.get(CONF_SW_VERSION)
            ),
        }

    @staticmethod
    def _identity_mismatch(entry: ConfigEntry, probe: RecameraProbeResult) -> bool:
        """Return whether authentication reached a different device."""
        return probe_identity_mismatch(
            entry.data,
            getattr(entry, "unique_id", None),
            probe.info,
        )

    @staticmethod
    def _stable_identity(probe: RecameraProbeResult) -> str | None:
        """Return a hardware identity suitable for a new config entry."""
        return probe.info.serial_number or probe.info.mac_address

    def _discovery_identity_mismatch(self, probe: RecameraProbeResult) -> bool:
        """Reject a discovery whose advertised hardware identity changed."""
        if self._discovery_mac:
            return self._discovery_mac != probe.info.mac_address
        if self._discovery_serial:
            return self._discovery_serial != probe.info.serial_number
        return False

    def _canonical_discovery_identity(self) -> str | None:
        """Return the same canonical identity used by a config entry."""
        if self._discovery_serial:
            return self._discovery_serial
        if self._discovery_mac:
            return self._discovery_mac
        return self._discovery_id

    @staticmethod
    def _title(probe: RecameraProbeResult, *, host: str | None = None) -> str:
        """Return the canonical user-facing device title."""
        return device_title(
            probe.info.serial_number,
            probe.info.mac_address,
            fallback=host,
        )
