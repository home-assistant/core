"""Config flow for ISEO Argo BLE Lock."""

from __future__ import annotations

import logging
import uuid as uuid_module
from typing import Any

import voluptuous as vol
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import ec

from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_ble_device_from_address,
    async_discovered_service_info,
)
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
    callback,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from iseo_argo_ble import IseoAuthError, IseoClient, IseoConnectionError, UserSubType, is_iseo_advertisement

from .const import (
    CONF_ADDRESS,
    CONF_ADMIN_PRIV_SCALAR,
    CONF_ADMIN_UUID,
    CONF_PRIV_SCALAR,
    CONF_USER_MAP,
    CONF_USER_SUBTYPE,
    CONF_UUID,
    DEFAULT_USER_SUBTYPE,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def _generate_identity() -> ec.EllipticCurvePrivateKey:
    """Generate a fresh SECP224R1 private key for use as an Argo BT identity."""
    priv = ec.generate_private_key(ec.SECP224R1(), default_backend())
    if not isinstance(priv, ec.EllipticCurvePrivateKey):
        raise TypeError("Expected EllipticCurvePrivateKey")
    return priv


def _discover_locks(hass: HomeAssistant) -> list[BluetoothServiceInfoBleak]:
    """Query HA's bluetooth integration for nearby ISEO locks."""
    all_devices = sorted(
        async_discovered_service_info(hass, connectable=True),
        key=lambda i: i.rssi,
        reverse=True,
    )
    _LOGGER.debug(
        "HA bluetooth cache — %d connectable device(s) visible", len(all_devices)
    )

    found: list[BluetoothServiceInfoBleak] = []
    for info in all_devices:
        if not is_iseo_advertisement(list(info.service_uuids or [])):
            continue
        _LOGGER.debug(
            "  %s  name=%r  rssi=%d — ISEO lock",
            info.address,
            info.name,
            info.rssi,
        )
        found.append(info)

    return found


class IseoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle config flow for ISEO Argo BLE Lock."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> IseoOptionsFlow:
        """Return the options flow."""
        return IseoOptionsFlow()

    def __init__(self) -> None:
        """Initialize."""
        self._discovered: dict[str, BluetoothServiceInfoBleak] = {}
        self._address: str = ""
        self._device_name: str = ""
        self._uuid_hex: str = ""
        self._priv_scalar: str = ""
        self._gw_priv: ec.EllipticCurvePrivateKey | None = None
        self._admin_priv: ec.EllipticCurvePrivateKey | None = None
        self._user_subtype: int = DEFAULT_USER_SUBTYPE
        self._bt_users: list[Any] = []
        self._user_map: dict[str, str] = {}
        self._admin_uuid_hex: str = ""
        self._admin_priv_scalar: str = ""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick a lock from HA's BLE cache."""
        errors: dict[str, str] = {}

        if user_input is not None and CONF_ADDRESS in user_input:
            address = user_input[CONF_ADDRESS]

            await self.async_set_unique_id(address.replace(":", ""))

            priv = _generate_identity()
            priv_int = priv.private_numbers().private_value  # type: ignore[attr-defined]
            new_uuid = uuid_module.uuid4().bytes

            self._address = address
            self._device_name = (
                self._discovered[address].name
                if address in self._discovered
                else ""
            )
            self._uuid_hex = new_uuid.hex()
            self._priv_scalar = hex(priv_int)
            self._gw_priv = priv
            self._user_subtype = UserSubType.BT_GATEWAY

            return await self.async_step_gw_register()

        found = _discover_locks(self.hass)
        self._discovered = {info.address: info for info in found}

        if not self._discovered:
            errors["base"] = "no_devices_found"
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema({}),
                errors=errors,
            )

        configured = {
            entry.data.get(CONF_ADDRESS)
            for entry in self._async_current_entries()
        }

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                {
                                    "value": info.address,
                                    "label": (
                                        f"{info.name or 'Unknown'}  —  {info.address}"
                                        f"  (RSSI {info.rssi} dBm)"
                                        + (
                                            " — already configured"
                                            if info.address in configured
                                            else ""
                                        )
                                    ),
                                }
                                for info in found
                            ],
                            mode=SelectSelectorMode.LIST,
                        )
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Called by HA when a matching BLE advertisement is seen."""
        await self.async_set_unique_id(discovery_info.address.replace(":", ""))
        self._abort_if_unique_id_configured()

        if not is_iseo_advertisement(list(discovery_info.service_uuids or [])):
            return self.async_abort(reason="not_iseo_device")

        priv = _generate_identity()
        priv_int = priv.private_numbers().private_value  # type: ignore[attr-defined]
        new_uuid = uuid_module.uuid4().bytes

        self._address = discovery_info.address
        self._device_name = discovery_info.name or discovery_info.address
        self._uuid_hex = new_uuid.hex()
        self._priv_scalar = hex(priv_int)
        self._gw_priv = priv
        self._user_subtype = UserSubType.BT_GATEWAY

        self.context["title_placeholders"] = {"name": self._device_name}
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm the discovered lock before proceeding to enrollment."""
        if user_input is not None:
            return await self.async_step_gw_register()

        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={"name": self._device_name},
        )

    async def async_step_gw_register(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Register the UUID as a Gateway (requires Master Card)."""
        errors: dict[str, str] = {}
        if user_input is not None:
            client = IseoClient(
                address=self._address,
                uuid_bytes=bytes.fromhex(self._uuid_hex),
                identity_priv=self._gw_priv,
                subtype=self._user_subtype,
                ble_device=async_ble_device_from_address(
                    self.hass, self._address, connectable=True
                ),
            )
            try:
                await client.register_user(name="Home Assistant")
                return await self.async_step_gw_register_logs()
            except (IseoConnectionError, IseoAuthError) as exc:
                _LOGGER.error("Gateway registration failed: %s", exc)
                errors["base"] = "auth_failed"

        return self.async_show_form(
            step_id="gw_register",
            description_placeholders={"uuid": self._uuid_hex.upper()},
            errors=errors,
        )

    async def async_step_gw_register_logs(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Enable log notifications for the Gateway (requires Master Card)."""
        errors: dict[str, str] = {}
        if user_input is not None:
            client = IseoClient(
                address=self._address,
                uuid_bytes=bytes.fromhex(self._uuid_hex),
                identity_priv=self._gw_priv,
                subtype=self._user_subtype,
                ble_device=async_ble_device_from_address(
                    self.hass, self._address, connectable=True
                ),
            )
            try:
                await client.gw_register_log_notif()
                return await self.async_step_gw_fetch_users()
            except (IseoConnectionError, IseoAuthError) as exc:
                _LOGGER.error("Gateway log registration failed: %s", exc)
                errors["base"] = "auth_failed"
            except Exception:
                _LOGGER.exception("Unexpected error during Gateway log registration")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="gw_register_logs",
            data_schema=vol.Schema({}),
            errors=errors,
        )

    async def async_step_gw_fetch_users(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Fetch the user list from the lock (requires Master Card)."""
        errors: dict[str, str] = {}
        if user_input is not None:
            client = IseoClient(
                address=self._address,
                uuid_bytes=bytes.fromhex(self._uuid_hex),
                identity_priv=self._gw_priv,
                subtype=self._user_subtype,
                ble_device=async_ble_device_from_address(
                    self.hass, self._address, connectable=True
                ),
            )
            try:
                self._bt_users = await client.read_users(skip_login=True)
                return await self.async_step_map_users()
            except (IseoConnectionError, IseoAuthError) as exc:
                _LOGGER.error("Failed to fetch users: %s", exc)
                errors["base"] = "auth_failed"

        return self.async_show_form(
            step_id="gw_fetch_users",
            data_schema=vol.Schema({}),
            errors=errors,
        )

    async def async_step_map_users(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Map Argo users to HA accounts."""
        if user_input is not None:
            skip_mapping = user_input.pop("ignore_all", False)
            if not skip_mapping:
                self._user_map = {
                    uuid_key: ha_uid
                    for uuid_key, ha_uid in user_input.items()
                    if ha_uid
                }
            return await self.async_step_admin_choice()

        ha_users = await self.hass.auth.async_get_users()
        ha_user_options = [
            {"value": u.id, "label": u.name or u.id}
            for u in ha_users
            if not u.system_generated and u.is_active
        ]

        fields: dict[Any, Any] = {vol.Optional("ignore_all", default=False): bool}
        for u in self._bt_users:
            label = u.name or u.uuid_hex[:8]
            fields[
                vol.Optional(u.uuid_hex.lower(), description={"label": label})
            ] = SelectSelector(
                SelectSelectorConfig(
                    options=ha_user_options,
                    mode=SelectSelectorMode.DROPDOWN,
                )
            )

        return self.async_show_form(
            step_id="map_users",
            data_schema=vol.Schema(fields),
        )

    async def async_step_admin_choice(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose how to handle administrative tasks."""
        if user_input is not None:
            choice = user_input["admin_choice"]
            if choice == "persistent":
                return await self.async_step_admin_setup()
            return self._async_create_iseo_entry()

        return self.async_show_form(
            step_id="admin_choice",
            data_schema=vol.Schema(
                {
                    vol.Required("admin_choice", default="persistent"): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                {
                                    "value": "persistent",
                                    "label": "Setup a persistent Admin identity (Automatic)",
                                },
                                {
                                    "value": "none",
                                    "label": "Finish setup (Logs only)",
                                },
                            ],
                            mode=SelectSelectorMode.LIST,
                            translation_key="admin_choice",
                        )
                    ),
                }
            ),
        )

    async def async_step_admin_setup(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Trigger Admin Identity generation."""
        if not self._admin_uuid_hex:
            priv = _generate_identity()
            priv_int = priv.private_numbers().private_value  # type: ignore[attr-defined]
            new_uuid = uuid_module.uuid4().bytes

            self._admin_uuid_hex = new_uuid.hex()
            self._admin_priv_scalar = hex(priv_int)
            self._admin_priv = priv

        return await self.async_step_admin_enroll()

    async def async_step_admin_enroll(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show generated UUID and enroll via Open command."""
        errors: dict[str, str] = {}
        if user_input is not None:
            client = IseoClient(
                address=self._address,
                uuid_bytes=bytes.fromhex(self._admin_uuid_hex),
                identity_priv=self._admin_priv,
                subtype=UserSubType.BT_SMARTPHONE,
                ble_device=async_ble_device_from_address(
                    self.hass, self._address, connectable=True
                ),
            )
            try:
                await client.open_lock()
                return self._async_create_iseo_entry()
            except (IseoConnectionError, IseoAuthError) as exc:
                _LOGGER.error("Admin enrollment failed: %s", exc)
                errors["base"] = "auth_failed"

        return self.async_show_form(
            step_id="admin_enroll",
            data_schema=vol.Schema({}),
            description_placeholders={"uuid": self._admin_uuid_hex.upper()},
            errors=errors,
        )

    def _async_create_iseo_entry(self) -> ConfigFlowResult:
        """Create the final config entry."""
        data: dict[str, Any] = {
            CONF_ADDRESS: self._address,
            CONF_UUID: self._uuid_hex,
            CONF_PRIV_SCALAR: self._priv_scalar,
            CONF_USER_SUBTYPE: self._user_subtype,
        }
        if self._admin_uuid_hex and self._admin_priv_scalar:
            data[CONF_ADMIN_UUID] = self._admin_uuid_hex
            data[CONF_ADMIN_PRIV_SCALAR] = self._admin_priv_scalar

        return self.async_create_entry(
            title=self._device_name or f"ISEO Lock ({self._address})",
            data=data,
            options={
                CONF_USER_MAP: self._user_map,
            },
        )


class IseoOptionsFlow(OptionsFlow):
    """Options flow for managing Argo user mappings and admin identity."""

    def __init__(self) -> None:
        """Initialize."""
        self._bt_users: list[Any] = []
        self._admin_uuid_hex: str = ""
        self._admin_priv_scalar: str = ""
        self._admin_priv: ec.EllipticCurvePrivateKey | None = None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Menu to choose between User Management and Admin Identity."""
        if user_input is not None:
            choice = user_input["management_choice"]
            if choice == "users":
                return await self.async_step_user_management_refresh()
            return await self.async_step_admin_identity()

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "management_choice", default="users"
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                {"value": "users", "label": "Manage User Mappings"},
                                {"value": "admin", "label": "Manage Admin Identity"},
                            ],
                            mode=SelectSelectorMode.LIST,
                            translation_key="management_choice",
                        )
                    )
                }
            ),
        )

    async def async_step_user_management_refresh(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Refresh user list from the lock."""
        errors: dict[str, str] = {}
        has_admin = CONF_ADMIN_UUID in self.config_entry.data

        if user_input is None and has_admin:
            user_input = {}

        if user_input is not None:
            from . import IseoRuntimeData  # noqa: PLC0415

            entry_data: IseoRuntimeData | None = getattr(
                self.config_entry, "runtime_data", None
            )
            coordinator = entry_data.coordinator if entry_data else None

            try:
                if has_admin:
                    if coordinator:
                        admin_client = await self.hass.async_add_executor_job(
                            coordinator.make_admin_client
                        )
                    else:
                        priv_int = int(
                            self.config_entry.data[CONF_ADMIN_PRIV_SCALAR], 16
                        )
                        admin_priv = await self.hass.async_add_executor_job(
                            ec.derive_private_key,
                            priv_int,
                            ec.SECP224R1(),
                            default_backend(),
                        )
                        admin_client = IseoClient(
                            address=self.config_entry.data[CONF_ADDRESS],
                            uuid_bytes=bytes.fromhex(
                                self.config_entry.data[CONF_ADMIN_UUID]
                            ),
                            identity_priv=admin_priv,
                            subtype=UserSubType.BT_SMARTPHONE,
                        )
                    if admin_client is not None:
                        admin_client.update_ble_device(
                            async_ble_device_from_address(
                                self.hass,
                                self.config_entry.data[CONF_ADDRESS],
                                connectable=True,
                            )
                        )
                        self._bt_users = await admin_client.read_users(
                            skip_login=False
                        )
                else:
                    if coordinator:
                        gw_client = coordinator.client
                    else:
                        priv_int = int(
                            self.config_entry.data[CONF_PRIV_SCALAR], 16
                        )
                        priv = await self.hass.async_add_executor_job(
                            ec.derive_private_key,
                            priv_int,
                            ec.SECP224R1(),
                            default_backend(),
                        )
                        gw_client = IseoClient(
                            address=self.config_entry.data[CONF_ADDRESS],
                            uuid_bytes=bytes.fromhex(
                                self.config_entry.data[CONF_UUID]
                            ),
                            identity_priv=priv,
                            subtype=self.config_entry.data.get(
                                CONF_USER_SUBTYPE, UserSubType.BT_GATEWAY
                            ),
                        )
                    gw_client.update_ble_device(
                        async_ble_device_from_address(
                            self.hass,
                            self.config_entry.data[CONF_ADDRESS],
                            connectable=True,
                        )
                    )
                    self._bt_users = await gw_client.read_users(skip_login=True)

                return await self.async_step_map_users()
            except (IseoConnectionError, IseoAuthError) as exc:
                _LOGGER.error("Failed to refresh users: %s", exc)
                errors["base"] = "auth_failed"

        return self.async_show_form(
            step_id="user_management_refresh",
            data_schema=vol.Schema({}),
            errors=errors,
        )

    async def async_step_admin_identity(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage (link/unlink) an admin phone identity."""
        if user_input is not None:
            choice = user_input["admin_action"]
            if choice == "remove":
                new_data = dict(self.config_entry.data)
                new_data.pop(CONF_ADMIN_UUID, None)
                new_data.pop(CONF_ADMIN_PRIV_SCALAR, None)
                self.hass.config_entries.async_update_entry(
                    self.config_entry, data=new_data
                )
                return self.async_create_entry(title="", data={})

            if choice == "setup":
                priv = _generate_identity()
                priv_int = priv.private_numbers().private_value  # type: ignore[attr-defined]
                new_uuid = uuid_module.uuid4().bytes

                self._admin_uuid_hex = new_uuid.hex()
                self._admin_priv_scalar = hex(priv_int)
                self._admin_priv = priv

                return await self.async_step_admin_enroll()

            return self.async_create_entry(title="", data={})

        has_admin = CONF_ADMIN_UUID in self.config_entry.data
        options: list[dict[str, str]] = [
            {"value": "setup", "label": "Configure/Rotate Admin Identity"},
            {"value": "none", "label": "Keep current configuration"},
        ]
        if has_admin:
            options.insert(
                1, {"value": "remove", "label": "Remove existing admin identity"}
            )

        return self.async_show_form(
            step_id="admin_identity",
            data_schema=vol.Schema(
                {
                    vol.Required("admin_action", default="none"): SelectSelector(
                        SelectSelectorConfig(
                            options=options,
                            mode=SelectSelectorMode.LIST,
                            translation_key="admin_action",
                        )
                    ),
                }
            ),
        )

    async def async_step_admin_enroll(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show generated UUID and enroll via Open command."""
        errors: dict[str, str] = {}
        if user_input is not None:
            enroll_client = IseoClient(
                address=self.config_entry.data[CONF_ADDRESS],
                uuid_bytes=bytes.fromhex(self._admin_uuid_hex),
                identity_priv=self._admin_priv,
                subtype=UserSubType.BT_SMARTPHONE,
                ble_device=async_ble_device_from_address(
                    self.hass,
                    self.config_entry.data[CONF_ADDRESS],
                    connectable=True,
                ),
            )

            try:
                await enroll_client.open_lock()
                new_data = dict(self.config_entry.data)
                new_data[CONF_ADMIN_UUID] = self._admin_uuid_hex
                new_data[CONF_ADMIN_PRIV_SCALAR] = self._admin_priv_scalar
                self.hass.config_entries.async_update_entry(
                    self.config_entry, data=new_data
                )
                return self.async_create_entry(title="", data={})
            except (IseoConnectionError, IseoAuthError) as exc:
                _LOGGER.error("Admin enrollment failed: %s", exc)
                errors["base"] = "auth_failed"

        return self.async_show_form(
            step_id="admin_enroll",
            data_schema=vol.Schema({}),
            description_placeholders={"uuid": self._admin_uuid_hex.upper()},
            errors=errors,
        )

    async def async_step_map_users(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Map users to HA accounts."""
        if user_input is not None:
            mapping = {
                uuid_key: ha_uid
                for uuid_key, ha_uid in user_input.items()
                if ha_uid
            }
            return self.async_create_entry(
                title="", data={CONF_USER_MAP: mapping}
            )

        current_map: dict[str, str] = self.config_entry.options.get(
            CONF_USER_MAP, {}
        )

        ha_users = await self.hass.auth.async_get_users()
        ha_user_options = [
            {"value": u.id, "label": u.name or u.id}
            for u in ha_users
            if not u.system_generated and u.is_active
        ]

        fields: dict[Any, Any] = {}
        for u in self._bt_users:
            uuid_key = u.uuid_hex.lower()
            label = u.name or u.uuid_hex[:8]
            default = current_map.get(uuid_key)
            desc: dict[str, Any] = {"label": label}
            if default:
                desc["suggested_value"] = default
            fields[
                vol.Optional(uuid_key, description=desc)
            ] = SelectSelector(
                SelectSelectorConfig(
                    options=ha_user_options,
                    mode=SelectSelectorMode.DROPDOWN,
                )
            )

        return self.async_show_form(
            step_id="map_users",
            data_schema=vol.Schema(fields),
            description_placeholders={"count": str(len(self._bt_users))},
        )
