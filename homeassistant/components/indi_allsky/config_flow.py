"""Config flow for INDI Allsky integration."""

from collections.abc import Mapping
import logging
from typing import Any, override

from aioindiallsky import (
    IndiAllSkyAuthError,
    IndiAllSkyClient,
    IndiAllSkyConnectionError,
    IndiAllSkyTimeoutError,
)
import probatio

from homeassistant.config_entries import (
    SOURCE_IGNORE,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SSL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import DOMAIN
from .util import get_ssl_context, is_ip_address, normalize_host

_LOGGER = logging.getLogger(__name__)

ALTERNATE_PORT_PAIRS = (
    {80, 443},
    {443, 8443},
)


def _matches_server_name(entry: ConfigEntry, server_name: str | None) -> bool:
    """Return whether the entry title matches the discovered server name."""
    return bool(
        server_name
        and (
            entry.title == server_name
            or entry.title.startswith(f"{server_name} (")
            or entry.title.startswith(f"{server_name}:")
        )
    )


def _matches_instance_identity(
    entry: ConfigEntry,
    server_name: str | None,
    expected_unique_id: str | None = None,
) -> bool:
    """Return True if entry matches instance identity across fallback and MAC IDs."""
    if expected_unique_id and entry.unique_id == expected_unique_id:
        return True
    if server_name and entry.unique_id and entry.unique_id.endswith(f"_{server_name}"):
        return True
    if not _matches_server_name(entry, server_name):
        return False
    if entry.unique_id is None:
        return True
    return bool(
        entry.unique_id
        and entry.unique_id.count(":") == 5
        and "_" not in entry.unique_id
    )


STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.TEXT,
                autocomplete="host",
            ),
        ),
        probatio.Required(CONF_PORT, default=443): NumberSelector(
            NumberSelectorConfig(
                min=1,
                max=65535,
                mode=NumberSelectorMode.BOX,
            ),
        ),
        probatio.Optional(CONF_SSL, default=True): BooleanSelector(),
        probatio.Optional(CONF_VERIFY_SSL, default=True): BooleanSelector(),
    }
)


async def validate_input(hass: HomeAssistant, data: Mapping[str, Any]) -> None:
    """Validate that the user input allows us to connect to INDI Allsky."""
    client = IndiAllSkyClient(
        host=data[CONF_HOST],
        port=int(data[CONF_PORT]),
        ssl=get_ssl_context(
            data.get(CONF_SSL, True),
            data.get(CONF_VERIFY_SSL, True),
        ),
        session=async_get_clientsession(hass),
    )

    try:
        await client.fetch_image("latestimage")
    except IndiAllSkyAuthError as err:
        _LOGGER.error(
            "Authentication failed for INDI Allsky at %s:%s: %s",
            data[CONF_HOST],
            data[CONF_PORT],
            err,
        )
        raise InvalidAuth from err
    except (IndiAllSkyConnectionError, IndiAllSkyTimeoutError) as err:
        _LOGGER.error(
            "Cannot connect to INDI Allsky instance at %s:%s: %s",
            data[CONF_HOST],
            data[CONF_PORT],
            err,
        )
        raise CannotConnect from err
    except Exception as err:
        raise Unknown from err


class IndiAllSkyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for INDI Allsky."""

    VERSION = 1

    _discovered_data: dict[str, Any]
    _matching_hosts: set[str]
    _discovered_mac: str | None = None
    _discovered_original_mac: str | None = None
    _discovered_unique_id: str | None = None
    _discovered_port: int | None = None
    _fallback_unique_id: str | None = None

    def _async_migrate_entry_for_mac(
        self,
        instance_unique_id: str,
        formatted_mac: str | None,
        fallback_unique_id: str | None,
        server_name: str | None,
        matching_hosts: set[str],
    ) -> ConfigEntry | None:
        """Migrate legacy MAC or fallback unique ID entry to instance unique ID."""
        matching_fallback_ids = {fallback_unique_id} if fallback_unique_id else set()
        if server_name:
            matching_fallback_ids.update(f"{h}_{server_name}" for h in matching_hosts)
        for entry in self._async_current_entries(include_ignore=False):
            if (
                (
                    formatted_mac
                    and entry.unique_id == formatted_mac
                    and _matches_server_name(entry, server_name)
                )
                or (fallback_unique_id and entry.unique_id == fallback_unique_id)
                or (
                    entry.unique_id in matching_fallback_ids
                    and entry.data.get(CONF_HOST) in matching_hosts
                )
            ):
                self.hass.config_entries.async_update_entry(
                    entry, unique_id=instance_unique_id
                )
                return entry
        return None

    async def _async_check_and_adopt_existing_entry(
        self, host: str, port: int, matching_hosts: set[str] | None = None
    ) -> None:
        """Check for existing duplicate entries and adopt unique_id if needed."""
        check_hosts = (
            matching_hosts if matching_hosts and host in matching_hosts else {host}
        )
        if self.unique_id:
            server_name = self.context.get("title_placeholders", {}).get("name")
            fallback_unique_id = getattr(self, "_fallback_unique_id", None)
            mac = getattr(self, "_discovered_mac", None)
            if mac and (
                migrated_entry := self._async_migrate_entry_for_mac(
                    self.unique_id,
                    mac,
                    fallback_unique_id,
                    server_name,
                    check_hosts,
                )
            ):
                updates = {}
                discovered_data = getattr(self, "_discovered_data", None)
                if discovered_data:
                    updates = await self._async_calculate_mac_updates(
                        migrated_entry,
                        host,
                        port,
                        discovered_data.get(CONF_SSL, True),
                        check_hosts,
                    )
                self._abort_if_unique_id_configured(updates=updates)

            adoptable_entries = [
                entry
                for entry in self._async_current_entries(include_ignore=False)
                if (
                    entry.unique_id is None
                    or entry.unique_id
                    in {f"{h}:{entry.data[CONF_PORT]}" for h in check_hosts}
                )
                and entry.data[CONF_HOST] in check_hosts
            ]
            for entry in adoptable_entries:
                if entry.data[CONF_PORT] == port:
                    self.hass.config_entries.async_update_entry(
                        entry, unique_id=self.unique_id
                    )
                    break
            else:
                if getattr(self, "_discovered_mac", None):
                    for entry in adoptable_entries:
                        if {entry.data[CONF_PORT], port} not in ALTERNATE_PORT_PAIRS:
                            continue
                        if not _matches_server_name(entry, server_name):
                            continue
                        try:
                            await validate_input(self.hass, entry.data)
                        except CannotConnect, InvalidAuth, Unknown:
                            continue
                        self.hass.config_entries.async_update_entry(
                            entry, unique_id=self.unique_id
                        )
                        break
        self._abort_if_unique_id_configured()
        for check_host in check_hosts:
            self._async_abort_entries_match(
                {
                    CONF_HOST: check_host,
                    CONF_PORT: port,
                }
            )
        if (
            matching_hosts
            and host in matching_hosts
            and not getattr(self, "_discovered_mac", None)
            and port in (80, 443)
        ):
            alt_port = 443 if port == 80 else 80
            server_name = self.context.get("title_placeholders", {}).get("name")
            for check_host in check_hosts:
                for entry in self._async_current_entries(include_ignore=False):
                    if (
                        entry.data.get(CONF_HOST) == check_host
                        and entry.data.get(CONF_PORT) == alt_port
                        and _matches_instance_identity(
                            entry, server_name, self.unique_id
                        )
                    ):
                        self._async_abort_entries_match(
                            {
                                CONF_HOST: check_host,
                                CONF_PORT: alt_port,
                            }
                        )

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            user_input[CONF_HOST] = normalize_host(user_input[CONF_HOST])
            user_input[CONF_PORT] = int(user_input[CONF_PORT])
            matching_hosts = getattr(self, "_matching_hosts", None)
            discovered_unique_id = getattr(self, "_discovered_unique_id", None)
            discovered_port = getattr(self, "_discovered_port", None)
            if matching_hosts:
                if user_input[CONF_HOST] in matching_hosts and (
                    discovered_port is None
                    or user_input[CONF_PORT] == discovered_port
                    or {user_input[CONF_PORT], discovered_port} in ALTERNATE_PORT_PAIRS
                ):
                    await self.async_set_unique_id(discovered_unique_id)
                    self._discovered_mac = getattr(
                        self, "_discovered_original_mac", None
                    )
                else:
                    await self.async_set_unique_id(None)
                    self._discovered_mac = None
                    matching_hosts = None
            await self._async_check_and_adopt_existing_entry(
                user_input[CONF_HOST],
                user_input[CONF_PORT],
                matching_hosts,
            )

            try:
                await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                port = user_input[CONF_PORT]
                default_port = 443 if user_input.get(CONF_SSL, True) else 80
                host_str = (
                    f"{user_input[CONF_HOST]}:{port}"
                    if port != default_port
                    else user_input[CONF_HOST]
                )
                return self.async_create_entry(
                    title=f"INDI Allsky ({host_str})",
                    data=user_input,
                )

        suggested_values = user_input or getattr(self, "_discovered_data", None)
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, suggested_values
            ),
            errors=errors,
        )

    def _async_find_matching_ignored_entry(
        self,
        fallback_id: str,
        matching_hosts: set[str],
        host: str,
        port: int,
        instance_unique_id: str | None = None,
        mac: str | None = None,
    ) -> ConfigEntry | None:
        """Find an existing ignored entry matching known server identities."""
        for entry in self._async_current_entries(include_ignore=True):
            if entry.source == SOURCE_IGNORE and (
                entry.unique_id in (fallback_id, f"{host}:{port}")
                or (mac and entry.unique_id == mac)
                or (instance_unique_id and entry.unique_id == instance_unique_id)
                or entry.unique_id in {f"{h}:{port}" for h in matching_hosts}
            ):
                return entry
        return None

    async def _async_adopt_entry_for_mac(
        self,
        instance_unique_id: str,
        port: int,
        matching_hosts: set[str],
        server_name: str | None = None,
    ) -> ConfigEntry | None:
        """Adopt an existing unassigned entry for the discovered instance."""
        adoptable_entries = [
            entry
            for entry in self._async_current_entries(include_ignore=False)
            if (
                entry.unique_id is None
                or entry.unique_id
                in {f"{h}:{entry.data[CONF_PORT]}" for h in matching_hosts}
            )
            and entry.data[CONF_HOST] in matching_hosts
        ]
        for entry in adoptable_entries:
            if entry.data[CONF_PORT] == port:
                self.hass.config_entries.async_update_entry(
                    entry, unique_id=instance_unique_id
                )
                return entry
        for entry in adoptable_entries:
            if {entry.data[CONF_PORT], port} not in ALTERNATE_PORT_PAIRS:
                continue
            if not _matches_server_name(entry, server_name):
                continue
            try:
                await validate_input(self.hass, entry.data)
            except CannotConnect, InvalidAuth, Unknown:
                continue
            self.hass.config_entries.async_update_entry(
                entry, unique_id=instance_unique_id
            )
            return entry
        return None

    async def _async_calculate_mac_updates(
        self,
        existing_entry: ConfigEntry,
        host: str,
        port: int,
        ssl: bool,
        matching_hosts: set[str],
    ) -> dict[str, Any]:
        """Calculate updates for an existing entry with matching MAC."""
        updates: dict[str, Any] = {}
        host_changed = (
            is_ip_address(existing_entry.data[CONF_HOST])
            and existing_entry.data[CONF_HOST] not in matching_hosts
        )
        target_host = host if host_changed else existing_entry.data[CONF_HOST]
        port_changed = existing_entry.data[CONF_PORT] != port

        if port_changed:
            if existing_entry.data[CONF_SSL] == ssl and not any(
                other.entry_id != existing_entry.entry_id
                and other.data.get(CONF_HOST) in (matching_hosts | {target_host})
                and other.data.get(CONF_PORT) == port
                for other in self._async_current_entries(include_ignore=False)
            ):
                try:
                    await validate_input(
                        self.hass,
                        {
                            **existing_entry.data,
                            CONF_HOST: target_host,
                            CONF_PORT: port,
                        },
                    )
                except CannotConnect, InvalidAuth, Unknown:
                    pass
                else:
                    if host_changed:
                        updates[CONF_HOST] = target_host
                    updates[CONF_PORT] = port
        elif host_changed:
            if not any(
                other.entry_id != existing_entry.entry_id
                and other.data.get(CONF_HOST) in (matching_hosts | {target_host})
                and other.data.get(CONF_PORT) == existing_entry.data[CONF_PORT]
                for other in self._async_current_entries(include_ignore=False)
            ):
                updates[CONF_HOST] = target_host
        return updates

    @override
    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery of an INDI Allsky server."""
        host = normalize_host(discovery_info.host)
        if discovery_info.type == "_http._tcp.local.":
            ssl = False
        elif discovery_info.type == "_https._tcp.local.":
            ssl = True
        elif "ssl" in discovery_info.properties:
            ssl = str(discovery_info.properties["ssl"]).lower() == "true"
        else:
            ssl = True

        port = discovery_info.port or (443 if ssl else 80)
        mac = discovery_info.properties.get("mac")

        matching_hosts = {normalize_host(addr) for addr in discovery_info.addresses}
        matching_hosts.add(host)
        if discovery_info.hostname:
            matching_hosts.add(normalize_host(discovery_info.hostname))
        self._matching_hosts = matching_hosts

        server_name = discovery_info.name.split("._")[0]
        stable_host = (
            normalize_host(discovery_info.hostname) if discovery_info.hostname else host
        )
        fallback_unique_id = f"{stable_host}_{server_name}"
        self._fallback_unique_id = fallback_unique_id
        self._discovered_port = port

        if mac:
            formatted_mac = format_mac(mac)
            instance_unique_id = f"{formatted_mac}_{server_name}"
            self._discovered_mac = formatted_mac
            self._discovered_original_mac = formatted_mac
            self._discovered_unique_id = instance_unique_id
            existing_entry = await self.async_set_unique_id(instance_unique_id)
            if existing_entry is None:
                existing_entry = self._async_migrate_entry_for_mac(
                    instance_unique_id,
                    formatted_mac,
                    fallback_unique_id,
                    server_name,
                    matching_hosts,
                )

            if existing_entry is None:
                if ignored_entry := self._async_find_matching_ignored_entry(
                    fallback_unique_id,
                    matching_hosts,
                    host,
                    port,
                    instance_unique_id,
                    formatted_mac,
                ):
                    existing_entry = ignored_entry

            if existing_entry is None:
                existing_entry = await self._async_adopt_entry_for_mac(
                    instance_unique_id, port, matching_hosts, server_name
                )

            if existing_entry is not None:
                if existing_entry.source == SOURCE_IGNORE or not existing_entry.data:
                    return self.async_abort(reason="already_configured")
                updates = await self._async_calculate_mac_updates(
                    existing_entry, host, port, ssl, matching_hosts
                )
            else:
                updates = {
                    CONF_HOST: host,
                    CONF_PORT: port,
                    CONF_SSL: ssl,
                }
            self._abort_if_unique_id_configured(updates=updates)
        else:
            self._discovered_unique_id = fallback_unique_id
            for entry in self._async_current_entries(include_ignore=False):
                if entry.data.get(CONF_HOST) in matching_hosts:
                    entry_port = entry.data.get(CONF_PORT)
                    if entry_port == port or (
                        {entry_port, port} == {80, 443}
                        and _matches_instance_identity(
                            entry, server_name, fallback_unique_id
                        )
                    ):
                        if entry.unique_id is None and not any(
                            other.unique_id == fallback_unique_id
                            for other in self._async_current_entries(
                                include_ignore=True
                            )
                        ):
                            self.hass.config_entries.async_update_entry(
                                entry, unique_id=fallback_unique_id
                            )
                        return self.async_abort(reason="already_configured")

            if self._async_find_matching_ignored_entry(
                fallback_unique_id, matching_hosts, host, port
            ):
                return self.async_abort(reason="already_configured")

            existing_entry = await self.async_set_unique_id(fallback_unique_id)
            updates = {}
            if existing_entry is not None:
                updates = await self._async_calculate_mac_updates(
                    existing_entry, host, port, ssl, matching_hosts
                )
            self._abort_if_unique_id_configured(updates=updates)

        self._discovered_data = {
            CONF_HOST: host,
            CONF_PORT: port,
            CONF_SSL: ssl,
            CONF_VERIFY_SSL: True,
        }
        self.context["title_placeholders"] = {"name": server_name}

        try:
            await validate_input(self.hass, self._discovered_data)
        except CannotConnect, InvalidAuth:
            if discovery_info.hostname:
                self._discovered_data[CONF_HOST] = normalize_host(
                    discovery_info.hostname
                )
            return await self.async_step_user()
        except Unknown:
            return self.async_abort(reason="unknown")

        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user confirmation of discovery."""
        if user_input is not None:
            await self._async_check_and_adopt_existing_entry(
                self._discovered_data[CONF_HOST],
                self._discovered_data[CONF_PORT],
                getattr(self, "_matching_hosts", None),
            )
            port = self._discovered_data[CONF_PORT]
            default_port = 443 if self._discovered_data[CONF_SSL] else 80
            host_str = (
                f"{self._discovered_data[CONF_HOST]}:{port}"
                if port != default_port
                else self._discovered_data[CONF_HOST]
            )
            return self.async_create_entry(
                title=f"INDI Allsky ({host_str})",
                data=self._discovered_data,
            )

        self._set_confirm_only()
        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders=self.context.get("title_placeholders", {}),
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class Unknown(HomeAssistantError):
    """Unexpected error."""
