"""Config flow for Philips TV integration."""

from collections.abc import Mapping
import platform
from typing import Any, override

from haphilipsjs import (
    DEFAULT_API_VERSION,
    ConnectionFailure,
    GeneralFailure,
    PairingFailure,
    PhilipsTV,
)
from haphilipsjs.typing import MenuItemsSettingsCurrentValueValue, MenuItemsSettingsNode
import probatio

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import (
    CONF_API_VERSION,
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PIN,
    CONF_USERNAME,
)
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from . import LOGGER
from .const import (
    CONF_ALLOW_NOTIFY,
    CONF_MENU_NODES,
    CONF_SYSTEM,
    CONST_APP_ID,
    CONST_APP_NAME,
    DOMAIN,
    MENU_NODE_TYPES,
)
from .coordinator import (
    EntitySetupData,
    PhilipsTVConfigEntry,
    PhilipsTVDataUpdateCoordinator,
)
from .helpers import SettingsNotAvailable, get_node_paths, get_path_names

USER_SCHEMA = probatio.Schema(
    {
        probatio.Required(
            CONF_HOST,
        ): str,
        probatio.Required(
            CONF_API_VERSION,
            default="1",
        ): probatio.In(["1", "5", "6"]),
    }
)


class PhilipsJSConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Philips TV."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize flow."""
        super().__init__()
        self._current: dict[str, Any] = {}
        self._hub: PhilipsTV | None = None
        self._pair_state: Any = None

    async def _async_attempt_prepare(
        self, host: str, api_version: int, secured_transport: bool
    ) -> None:
        hub = PhilipsTV(
            host, api_version=api_version, secured_transport=secured_transport
        )

        await hub.getSystem()
        await hub.setTransport(hub.secured_transport, hub.api_version_detected)

        if not hub.system or not hub.name:
            raise ConnectionFailure("System data or name is empty")

        self._hub = hub
        self._current[CONF_HOST] = host
        self._current[CONF_SYSTEM] = hub.system
        self._current[CONF_API_VERSION] = hub.api_version
        self.context.update({"title_placeholders": {CONF_NAME: hub.name}})

        if serialnumber := hub.system.get("serialnumber"):
            await self.async_set_unique_id(serialnumber)
            if self.source != SOURCE_REAUTH:
                self._abort_if_unique_id_configured(
                    updates=self._current, reload_on_update=True
                )

    async def _async_attempt_add(self) -> ConfigFlowResult:
        assert self._hub
        if self._hub.pairing_type == "digest_auth_pairing":
            return await self.async_step_pair()
        return await self._async_create_current()

    async def _async_create_current(self) -> ConfigFlowResult:
        system = self._current[CONF_SYSTEM]
        if self.source == SOURCE_REAUTH:
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(), data_updates=self._current
            )

        return self.async_create_entry(
            title=f"{system['name']} ({system['serialnumber']})",
            data=self._current,
        )

    async def async_step_pair(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Attempt to pair with device."""
        assert self._hub

        errors: dict[str, str] = {}
        schema = probatio.Schema(
            {
                probatio.Required(probatio.Secret(CONF_PIN)): str,
            }
        )

        if not user_input:
            try:
                self._pair_state = await self._hub.pairRequest(
                    CONST_APP_ID,
                    CONST_APP_NAME,
                    platform.node(),
                    platform.system(),
                    "native",
                )
            except PairingFailure as exc:
                LOGGER.debug(exc)
                return self.async_abort(
                    reason="pairing_failure",
                    description_placeholders={"error_id": exc.data.get("error_id")},
                )
            return self.async_show_form(
                step_id="pair", data_schema=schema, errors=errors
            )

        try:
            username, password = await self._hub.pairGrant(
                self._pair_state, user_input[CONF_PIN]
            )
        except PairingFailure as exc:
            LOGGER.debug(exc)
            if exc.data.get("error_id") == "INVALID_PIN":
                errors[CONF_PIN] = "invalid_pin"
                return self.async_show_form(
                    step_id="pair", data_schema=schema, errors=errors
                )

            return self.async_abort(
                reason="pairing_failure",
                description_placeholders={"error_id": exc.data.get("error_id")},
            )

        self._current[CONF_USERNAME] = username
        self._current[CONF_PASSWORD] = password
        return await self._async_create_current()

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle configuration by re-auth."""
        self._current[CONF_HOST] = entry_data[CONF_HOST]
        self._current[CONF_API_VERSION] = entry_data[CONF_API_VERSION]
        return await self.async_step_user()

    @override
    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""

        LOGGER.debug(
            "Checking discovered device: %s on %s",
            discovery_info.name,
            discovery_info.host,
        )

        secured_transport = discovery_info.type == "_philipstv_s_rpc._tcp.local."
        api_version = 6 if secured_transport else DEFAULT_API_VERSION

        try:
            await self._async_attempt_prepare(
                discovery_info.host, api_version, secured_transport
            )
        except GeneralFailure:
            LOGGER.debug("Failed to get system info from discovery", exc_info=True)
            return self.async_abort(reason="discovery_failure")

        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by zeroconf."""
        if user_input is not None:
            return await self._async_attempt_add()

        name = self.context.get("title_placeholders", {CONF_NAME: "Philips TV"})[
            CONF_NAME
        ]
        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders={CONF_NAME: name},
        )

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}
        if user_input:
            self._current = user_input
            try:
                await self._async_attempt_prepare(
                    user_input[CONF_HOST], int(user_input[CONF_API_VERSION]), False
                )
            except GeneralFailure as exc:
                LOGGER.error(exc)
                errors["base"] = "cannot_connect"
            else:
                return await self._async_attempt_add()

        schema = self.add_suggested_values_to_schema(USER_SCHEMA, self._current)
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    @override
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlowHandler:
        """Get the options flow for this handler."""
        return OptionsFlowHandler()


async def get_usable_nodes(
    api: PhilipsTV,
    paths: list[tuple[MenuItemsSettingsNode, ...]],
) -> list[tuple[MenuItemsSettingsNode, ...]]:
    """Filter out parent nodes that do not have an active node in their value."""
    parent_node_ids = [
        node["node_id"]
        for node, *_ in paths
        if node["type"] == "PARENT_NODE" and "nodes" in node.get("data", {})
    ]

    parent_node_current: dict[int, MenuItemsSettingsCurrentValueValue | None] = {}
    if data := await api.getMenuItemsSettingsCurrentValue(parent_node_ids):
        parent_node_current.update(data)

    def _accepted(node: MenuItemsSettingsNode) -> bool:
        if node["type"] not in MENU_NODE_TYPES:
            return False
        if node["type"] == "PARENT_NODE":
            current = parent_node_current.get(node["node_id"])
            return bool(current and current.get("data", {}).get("activenode_id"))
        return True

    return [path for path in paths if _accepted(path[0])]


async def _get_node_descriptions(api: PhilipsTV) -> dict[str, EntitySetupData]:
    """Fetch the node descriptions that can be exposed as entities."""
    paths = await get_usable_nodes(api, list(get_node_paths(api)))
    names = await get_path_names(api, paths)

    return {
        str(node["node_id"]): EntitySetupData(node=node, name=name)
        for (node, *_), name in zip(paths, names, strict=True)
    }


class OptionsFlowHandler(OptionsFlow):
    """Handle the options flow."""

    config_entry: PhilipsTVConfigEntry

    def __init__(self) -> None:
        """Initialize the options flow."""
        self.menu_nodes: dict[str, EntitySetupData] = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the options flow."""
        coordinator: PhilipsTVDataUpdateCoordinator = self.config_entry.runtime_data

        if user_input is not None:
            selected = [self.menu_nodes[key] for key in user_input[CONF_MENU_NODES]]
            return self.async_create_entry(
                data={
                    CONF_ALLOW_NOTIFY: user_input[CONF_ALLOW_NOTIFY],
                    CONF_MENU_NODES: selected,
                }
            )

        try:
            self.menu_nodes = await _get_node_descriptions(coordinator.api)
        except SettingsNotAvailable, ConnectionFailure, GeneralFailure:
            return self.async_abort(reason="cannot_connect")

        options = self.config_entry.options
        selected_default = [
            str(description["node"]["node_id"])
            for description in options.get(CONF_MENU_NODES, [])
            if str(description["node"]["node_id"]) in self.menu_nodes
        ]

        schema = probatio.Schema(
            {
                probatio.Required(
                    CONF_ALLOW_NOTIFY,
                    default=options.get(CONF_ALLOW_NOTIFY, False),
                ): selector.BooleanSelector(),
                probatio.Required(
                    CONF_MENU_NODES, default=selected_default
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(value=node_id, label=data["name"])
                            for node_id, data in self.menu_nodes.items()
                        ],
                        multiple=True,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
