"""Config flow for Candy House Sesame BLE integration."""

import asyncio
import contextlib
import logging
import re
from typing import Any, override
import uuid

from bleak.backends.device import BLEDevice
import probatio

from homeassistant import config_entries
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_ble_device_from_address,
    async_discovered_service_info,
    async_last_service_info,
)

try:
    from homeassistant.components.file_upload import process_uploaded_file

    _FILE_UPLOAD_AVAILABLE = True
except ImportError:  # pragma: no cover
    _FILE_UPLOAD_AVAILABLE = False

try:
    from homeassistant.components.qrcode import decode_qr_image

    _QRCODE_AVAILABLE = True
except ImportError:  # pragma: no cover
    _QRCODE_AVAILABLE = False

from pysesame_ble import (
    ProductModels,
    SesameAdData,
    SesameAuthenticationError,
    SesameDevice,
    SesameKeyError,
    SesameQRCode,
    get_sesame_mfg_data,
)

from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import selector
from homeassistant.helpers.device_registry import format_mac

from .const import (
    CONF_DEVICE_UUID,
    CONF_QR_URL,
    CONF_SECRET_KEY,
    DOMAIN,
    FRIENDLY_MODELS,
    SUPPORTED_LOCK_MODELS,
)

logger = logging.getLogger(__name__)


_MAC_REGEX = re.compile(
    r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$|^([0-9A-Fa-f]{2}-){5}[0-9A-Fa-f]{2}$"
)
_PASSWORD_SELECTOR = selector.TextSelector(
    selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
)


def _is_valid_mac_address(mac: str | None) -> bool:
    """Return True if mac is a valid 6-octet Bluetooth MAC address with consistent separators."""
    if not mac:
        return False
    return bool(_MAC_REGEX.match(mac.strip()))


def _is_valid_hex_key(key: str | None) -> bool:
    """Return True if key is a 32-character hex string."""
    if not key or len(key) != 32:
        return False
    try:
        decoded = bytes.fromhex(key)
        return len(decoded) == 16
    except ValueError:
        return False


def _decode_uploaded_qr(hass: HomeAssistant, uploaded_file_id: str) -> str | None:
    """Read and decode the uploaded QR image in the executor."""
    if not _QRCODE_AVAILABLE:
        return None
    try:
        with process_uploaded_file(hass, uploaded_file_id) as file_path:
            results = decode_qr_image(file_path)
            for url in results:
                if url.startswith("ssm://"):
                    return url
    except Exception as err:  # noqa: BLE001
        logger.debug("Error decoding QR image: %s", err)
    return None


class SesameBLEConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sesame BLE."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        super().__init__()
        self._qr_code_info: SesameQRCode | None = None
        self._mac_address: str | None = None
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._sesame_adv_data: SesameAdData | None = None

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step by showing options menu."""
        return self.async_show_menu(
            step_id="user",
            menu_options=["discover_unregistered", "import_qr", "manual"],
        )

    async def async_step_discover_unregistered(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle discovery and registration of unregistered Sesame BLE devices."""
        errors: dict[str, str] = {}

        if user_input is not None and "mac_address" in user_input:
            mac_address: str = user_input["mac_address"]
            self._mac_address = mac_address

            discovered_info = None
            last_info = async_last_service_info(
                self.hass, mac_address, connectable=True
            )
            if last_info and get_sesame_mfg_data(
                getattr(last_info.advertisement, "manufacturer_data", {})
            ):
                discovered_info = last_info
            else:
                for service_info in async_discovered_service_info(self.hass):
                    if service_info.address == self._mac_address:
                        discovered_info = service_info
                        break

            if not discovered_info:
                errors["base"] = "device_not_found"
            else:
                mfg_tuple = get_sesame_mfg_data(
                    discovered_info.advertisement.manufacturer_data
                )
                if not mfg_tuple:
                    errors["base"] = "invalid_mfg_data"
                else:
                    _, mfg_data = mfg_tuple
                    try:
                        sesame_adv_data = SesameAdData.decode(mfg_data)
                        model_name = ProductModels(sesame_adv_data.model_id).name
                        if model_name not in SUPPORTED_LOCK_MODELS:
                            errors["base"] = "unsupported_model"
                        elif sesame_adv_data.is_registered:
                            self._discovery_info = discovered_info
                            self._sesame_adv_data = sesame_adv_data
                            return await self.async_step_bluetooth_confirm()
                    except ValueError, KeyError, IndexError:
                        errors["base"] = "invalid_mfg_data"

                if not errors:
                    formatted_mac = format_mac(self._mac_address)
                    await self.async_set_unique_id(formatted_mac)
                    self._abort_if_unique_id_configured()

                    device = SesameDevice(discovered_info.device, sesame_adv_data)
                    try:
                        async with asyncio.timeout(15.0):
                            await device.connect()
                            secret_key_hex = await device.register()
                    except Exception:
                        logger.exception("Registration failed over BLE")
                        errors["base"] = "registration_failed"
                    finally:
                        with contextlib.suppress(Exception):
                            await device.disconnect()

                    if not errors:
                        friendly_model = FRIENDLY_MODELS.get(model_name, model_name)
                        return self.async_create_entry(
                            title=f"Sesame {friendly_model} ({self._mac_address[-5:]})",
                            data={
                                "mac_address": self._mac_address,
                                CONF_SECRET_KEY: secret_key_hex,
                                CONF_MODEL: model_name,
                                CONF_DEVICE_UUID: str(sesame_adv_data.device_uuid),
                            },
                        )

        discovered_options = {}
        for service_info in async_discovered_service_info(self.hass, connectable=True):
            mfg_tuple = get_sesame_mfg_data(
                service_info.advertisement.manufacturer_data
            )
            if mfg_tuple:
                cid, mfg_data = mfg_tuple
                try:
                    sesame_adv_data = SesameAdData.decode(mfg_data)
                    logger.debug(
                        "Found candidate Sesame BLE advertisement: CID=0x%04X, model_id=%s, is_registered=%s",
                        cid,
                        sesame_adv_data.model_id,
                        sesame_adv_data.is_registered,
                    )
                    if not sesame_adv_data.is_registered:
                        model_name = ProductModels(sesame_adv_data.model_id).name
                        if model_name in SUPPORTED_LOCK_MODELS:
                            friendly_model = FRIENDLY_MODELS.get(model_name, model_name)
                            discovered_options[service_info.address] = (
                                f"Sesame {friendly_model} ({service_info.name or service_info.address})"
                            )
                except (ValueError, KeyError, IndexError) as err:
                    logger.warning(
                        "Failed to decode Sesame manufacturer data for %s: %s",
                        service_info.address,
                        err,
                    )

        if not discovered_options:
            errors.setdefault("base", "no_unregistered_devices")
            return self.async_show_form(
                step_id="discover_unregistered",
                data_schema=probatio.Schema({}),
                errors=errors,
            )

        return self.async_show_form(
            step_id="discover_unregistered",
            data_schema=probatio.Schema(
                {probatio.Required("mac_address"): probatio.In(discovered_options)}
            ),
            errors=errors,
        )

    def _find_matching_qr_device(
        self, target_uuid: uuid.UUID
    ) -> tuple[BluetoothServiceInfoBleak | None, SesameAdData | None, str | None]:
        """Find discovered Bluetooth device matching QR code UUID."""
        for service_info in async_discovered_service_info(self.hass, connectable=True):
            if mfg_tuple := get_sesame_mfg_data(
                getattr(service_info.advertisement, "manufacturer_data", {})
            ):
                _, mfg_data = mfg_tuple
                with contextlib.suppress(ValueError, KeyError, IndexError):
                    sesame_adv_data = SesameAdData.decode(mfg_data)
                    if sesame_adv_data.device_uuid == target_uuid:
                        try:
                            adv_model = ProductModels(sesame_adv_data.model_id).name
                        except ValueError:
                            adv_model = None

                        if not adv_model or adv_model not in SUPPORTED_LOCK_MODELS:
                            return None, None, "unsupported_model"
                        if (
                            self._qr_code_info
                            and sesame_adv_data.model_id != self._qr_code_info.model_id
                        ):
                            return None, None, "qr_device_mismatch"

                        return service_info, sesame_adv_data, None

        return None, None, None

    async def async_step_import_qr(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle QR code or setup URL import."""
        errors: dict[str, str] = {}

        if user_input is not None:
            qr_code_image = user_input.get("qr_code_image")
            qr_url = user_input.get(CONF_QR_URL)

            if not qr_code_image and not qr_url:
                errors["base"] = "invalid_qr_code"
            elif qr_code_image:
                if (
                    not _FILE_UPLOAD_AVAILABLE or not _QRCODE_AVAILABLE
                ):  # pragma: no cover
                    errors["base"] = "invalid_qr_code"
                else:
                    qr_url = await self.hass.async_add_executor_job(
                        _decode_uploaded_qr, self.hass, qr_code_image
                    )
                    if not qr_url:
                        errors["base"] = "invalid_qr_code"

            if not errors and qr_url:
                try:
                    self._qr_code_info = SesameQRCode.from_url(qr_url)
                    model_name = ProductModels(self._qr_code_info.model_id).name
                    if model_name not in SUPPORTED_LOCK_MODELS:
                        errors["base"] = "unsupported_model"
                except Exception as err:  # noqa: BLE001
                    logger.debug("Failed to parse QR code URL: %s", err)
                    errors["base"] = "invalid_qr_code"

                if not errors:
                    assert self._qr_code_info is not None
                    found_info, found_adv_data, error_key = (
                        self._find_matching_qr_device(self._qr_code_info.device_uuid)
                    )
                    if error_key:
                        errors["base"] = error_key
                    elif found_info:
                        self._mac_address = found_info.address
                        formatted_mac = format_mac(self._mac_address)
                        await self.async_set_unique_id(formatted_mac)
                        self._abort_if_unique_id_configured()
                        if found_adv_data and not found_adv_data.is_registered:
                            model_name = ProductModels(found_adv_data.model_id).name
                            friendly_model = FRIENDLY_MODELS.get(model_name, model_name)
                            self.context = {
                                **self.context,
                                "title_placeholders": {
                                    "name": f"Sesame {friendly_model} ({self._mac_address[-5:]})"
                                },
                            }
                            self._discovery_info = found_info
                            self._sesame_adv_data = found_adv_data
                            return await self.async_step_bluetooth_register_confirm()

                        self._discovery_info = found_info
                        self._sesame_adv_data = found_adv_data
                        if auth_error := await self._async_validate_bluetooth_key(
                            found_info.device, self._qr_code_info.secret_key.hex()
                        ):
                            errors["base"] = auth_error
                        else:
                            model_name = ProductModels(self._qr_code_info.model_id).name
                            friendly_model = FRIENDLY_MODELS.get(model_name, model_name)
                            return self.async_create_entry(
                                title=self._qr_code_info.device_name
                                or f"Sesame {friendly_model}",
                                data={
                                    "mac_address": self._mac_address,
                                    CONF_SECRET_KEY: self._qr_code_info.secret_key.hex(),
                                    CONF_MODEL: model_name,
                                    CONF_DEVICE_UUID: str(
                                        self._qr_code_info.device_uuid
                                    ),
                                },
                            )
                    else:
                        return await self.async_step_select_address()

        return self.async_show_form(
            step_id="import_qr",
            data_schema=probatio.Schema(
                {
                    **(
                        {
                            probatio.Optional("qr_code_image"): selector.FileSelector(
                                selector.FileSelectorConfig(accept="image/*")
                            )
                        }
                        if _FILE_UPLOAD_AVAILABLE and _QRCODE_AVAILABLE
                        else {}
                    ),
                    probatio.Optional(CONF_QR_URL): _PASSWORD_SELECTOR,
                }
            ),
            errors=errors,
        )

    def _async_show_manual_form(
        self, errors: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Show the manual configuration form."""
        model_options = [
            selector.SelectOptionDict(
                value=model.name,
                label=f"Sesame {FRIENDLY_MODELS.get(model.name, model.name)}",
            )
            for model in ProductModels
            if model.name in SUPPORTED_LOCK_MODELS
        ]
        return self.async_show_form(
            step_id="manual",
            data_schema=probatio.Schema(
                {
                    probatio.Required("mac_address"): str,
                    probatio.Required(CONF_SECRET_KEY): _PASSWORD_SELECTOR,
                    probatio.Required(
                        CONF_MODEL, default=ProductModels.SESAME5.name
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=model_options,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    probatio.Optional(CONF_DEVICE_UUID): str,
                }
            ),
            errors=errors,
        )

    def _validate_manual_advertisement(
        self,
        last_info: BluetoothServiceInfoBleak | None,
        model_name: str,
        parsed_uuid: uuid.UUID | None,
        errors: dict[str, str],
    ) -> tuple[SesameAdData | None, uuid.UUID | None]:
        """Validate advertisement data against user input in manual step."""
        adv_data = None
        if last_info and (
            mfg_tuple := get_sesame_mfg_data(
                getattr(last_info.advertisement, "manufacturer_data", {})
            )
        ):
            try:
                adv_data = SesameAdData.decode(mfg_tuple[1])
            except ValueError, KeyError, IndexError:
                pass
            else:
                try:
                    advertised_model = ProductModels(adv_data.model_id).name
                except ValueError:
                    advertised_model = None

                if (
                    not advertised_model
                    or advertised_model not in SUPPORTED_LOCK_MODELS
                ):
                    errors[CONF_MODEL] = "unsupported_model"
                elif advertised_model != model_name:
                    errors[CONF_MODEL] = "device_mismatch"

                if parsed_uuid and adv_data.device_uuid != parsed_uuid:
                    errors[CONF_DEVICE_UUID] = "device_mismatch"
                elif not parsed_uuid:
                    parsed_uuid = adv_data.device_uuid
        return adv_data, parsed_uuid

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual config entry validation."""
        errors: dict[str, str] = {}

        if user_input is None:
            return self._async_show_manual_form()

        mac_address = user_input.get("mac_address")
        secret_key = user_input.get(CONF_SECRET_KEY)
        model_name = user_input.get(CONF_MODEL)
        device_uuid_input = user_input.get(CONF_DEVICE_UUID)
        parsed_uuid: uuid.UUID | None = None

        if not _is_valid_mac_address(mac_address):
            errors["mac_address"] = "invalid_mac"
        elif not _is_valid_hex_key(secret_key):
            errors[CONF_SECRET_KEY] = "invalid_secret_key"
        elif model_name not in SUPPORTED_LOCK_MODELS:  # pragma: no cover
            errors[CONF_MODEL] = "unsupported_model"
        elif device_uuid_input and device_uuid_input.strip():
            try:
                parsed_uuid = uuid.UUID(device_uuid_input.strip())
            except ValueError:
                errors[CONF_DEVICE_UUID] = "invalid_device_uuid"

        if errors:
            return self._async_show_manual_form(errors)

        assert isinstance(mac_address, str)
        assert isinstance(secret_key, str)
        assert isinstance(model_name, str)
        formatted_mac = format_mac(mac_address.strip())
        canonical_mac = formatted_mac.upper()
        self._mac_address = canonical_mac
        await self.async_set_unique_id(formatted_mac)
        self._abort_if_unique_id_configured()
        last_info = async_last_service_info(self.hass, canonical_mac, connectable=False)
        connectable_info = async_last_service_info(
            self.hass, canonical_mac, connectable=True
        )
        if connectable_info:
            canonical_mac = connectable_info.address
            self._mac_address = canonical_mac
        elif last_info:
            canonical_mac = last_info.address
            self._mac_address = canonical_mac

        adv_data, parsed_uuid = self._validate_manual_advertisement(
            last_info, model_name, parsed_uuid, errors
        )

        if errors:
            return self._async_show_manual_form(errors)

        if adv_data and not adv_data.is_registered:
            if connectable_info:
                friendly_model = FRIENDLY_MODELS.get(model_name, model_name)
                self.context = {
                    **self.context,
                    "title_placeholders": {
                        "name": f"Sesame {friendly_model} ({canonical_mac[-5:]})"
                    },
                }
                self._discovery_info = connectable_info
                self._sesame_adv_data = adv_data
                return await self.async_step_bluetooth_register_confirm()
            errors["mac_address"] = "device_not_found"
            return self._async_show_manual_form(errors)

        if not parsed_uuid:
            errors[CONF_DEVICE_UUID] = "uuid_required"
            return self._async_show_manual_form(errors)

        ble_device = (
            connectable_info.device
            if connectable_info
            else async_ble_device_from_address(
                self.hass, canonical_mac, connectable=True
            )
        )
        if not ble_device:
            errors["mac_address"] = "device_not_found"
            return self._async_show_manual_form(errors)

        if adv_data:
            self._sesame_adv_data = adv_data
        else:
            product_model = ProductModels[model_name]
            self._sesame_adv_data = SesameAdData(
                model_id=product_model.value,
                is_registered=True,
                device_uuid=parsed_uuid,
            )

        if auth_error := await self._async_validate_bluetooth_key(
            ble_device, secret_key
        ):
            if auth_error == "invalid_auth":
                errors[CONF_SECRET_KEY] = "invalid_auth"
            else:
                errors["base"] = auth_error
            return self._async_show_manual_form(errors)

        friendly_model = FRIENDLY_MODELS.get(model_name, model_name)
        return self.async_create_entry(
            title=f"Sesame {friendly_model} ({canonical_mac[-5:]})",
            data={
                "mac_address": canonical_mac,
                CONF_SECRET_KEY: secret_key,
                CONF_MODEL: model_name,
                CONF_DEVICE_UUID: str(parsed_uuid),
            },
        )

    async def async_step_select_address(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step to select the BLE MAC address if QR code UUID cannot be resolved automatically."""
        if not self._qr_code_info:
            return self.async_abort(reason="unknown")
        qr_info = self._qr_code_info
        errors: dict[str, str] = {}

        if user_input is not None:
            mac_address = user_input["mac_address"]
            if not _is_valid_mac_address(mac_address):
                errors["mac_address"] = "invalid_mac"
            else:
                formatted_mac = format_mac(mac_address.strip())
                canonical_mac = formatted_mac.upper()
                last_info = async_last_service_info(
                    self.hass, canonical_mac, connectable=False
                )
                connectable_info = async_last_service_info(
                    self.hass, canonical_mac, connectable=True
                )
                if connectable_info:
                    canonical_mac = connectable_info.address
                elif last_info:
                    canonical_mac = last_info.address
                adv_data = None
                if last_info and (
                    mfg_tuple := get_sesame_mfg_data(
                        getattr(last_info.advertisement, "manufacturer_data", {})
                    )
                ):
                    _, mfg_data = mfg_tuple
                    with contextlib.suppress(ValueError, KeyError, IndexError):
                        adv_data = SesameAdData.decode(mfg_data)
                        if adv_data.device_uuid != qr_info.device_uuid:
                            errors["mac_address"] = "qr_device_mismatch"
                        else:
                            try:
                                adv_model = ProductModels(adv_data.model_id).name
                            except ValueError:
                                adv_model = None
                            if not adv_model or adv_model not in SUPPORTED_LOCK_MODELS:
                                errors["mac_address"] = "unsupported_model"
                            elif adv_data.model_id != qr_info.model_id:
                                errors["mac_address"] = "qr_device_mismatch"

                if not errors:
                    self._mac_address = canonical_mac
                    await self.async_set_unique_id(formatted_mac)
                    self._abort_if_unique_id_configured()

                    if adv_data and not adv_data.is_registered:
                        if connectable_info:
                            model_name = ProductModels(adv_data.model_id).name
                            friendly_model = FRIENDLY_MODELS.get(model_name, model_name)
                            self.context = {
                                **self.context,
                                "title_placeholders": {
                                    "name": f"Sesame {friendly_model} ({canonical_mac[-5:]})"
                                },
                            }
                            self._discovery_info = connectable_info
                            self._sesame_adv_data = adv_data
                            return await self.async_step_bluetooth_register_confirm()
                        errors["mac_address"] = "device_not_found"
                    else:
                        ble_device = (
                            connectable_info.device
                            if connectable_info
                            else async_ble_device_from_address(
                                self.hass, canonical_mac, connectable=True
                            )
                        )
                        if not ble_device:
                            errors["mac_address"] = "device_not_found"
                        else:
                            if adv_data:
                                self._sesame_adv_data = adv_data
                            else:
                                self._sesame_adv_data = SesameAdData(
                                    model_id=qr_info.model_id,
                                    is_registered=True,
                                    device_uuid=qr_info.device_uuid,
                                )
                            if auth_error := await self._async_validate_bluetooth_key(
                                ble_device, qr_info.secret_key.hex()
                            ):
                                if auth_error == "invalid_auth":
                                    errors["base"] = "invalid_auth"
                                else:
                                    errors["base"] = auth_error
                            else:
                                model_name = ProductModels(qr_info.model_id).name
                                friendly_model = FRIENDLY_MODELS.get(
                                    model_name, model_name
                                )
                                return self.async_create_entry(
                                    title=qr_info.device_name
                                    or f"Sesame {friendly_model}",
                                    data={
                                        "mac_address": canonical_mac,
                                        CONF_SECRET_KEY: qr_info.secret_key.hex(),
                                        CONF_MODEL: model_name,
                                        CONF_DEVICE_UUID: str(qr_info.device_uuid),
                                    },
                                )

        discovered_options = {}
        for service_info in async_discovered_service_info(self.hass, connectable=True):
            mfg_tuple = get_sesame_mfg_data(
                service_info.advertisement.manufacturer_data
            )
            if mfg_tuple:
                _, mfg_data = mfg_tuple
                with contextlib.suppress(ValueError, KeyError, IndexError):
                    sesame_adv_data = SesameAdData.decode(mfg_data)
                    model_name = ProductModels(sesame_adv_data.model_id).name
                    if (
                        model_name in SUPPORTED_LOCK_MODELS
                        and sesame_adv_data.device_uuid == qr_info.device_uuid
                    ):
                        friendly_model = FRIENDLY_MODELS.get(model_name, model_name)
                        discovered_options[service_info.address] = (
                            f"Sesame {friendly_model} ({service_info.name or service_info.address})"
                        )

        if not discovered_options:
            errors.setdefault("base", "no_devices_found")
            return self.async_show_form(
                step_id="select_address",
                data_schema=probatio.Schema({probatio.Required("mac_address"): str}),
                errors=errors,
            )

        return self.async_show_form(
            step_id="select_address",
            data_schema=probatio.Schema(
                {probatio.Required("mac_address"): probatio.In(discovered_options)}
            ),
            errors=errors,
        )

    @override
    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle bluetooth discovery."""
        mac_address = discovery_info.address
        formatted_mac = format_mac(mac_address)

        mfg_tuple = get_sesame_mfg_data(discovery_info.advertisement.manufacturer_data)
        if not mfg_tuple:
            return self.async_abort(reason="not_sesame")

        _, mfg_data = mfg_tuple
        try:
            sesame_adv_data = SesameAdData.decode(mfg_data)
            model_name = ProductModels(sesame_adv_data.model_id).name
            if model_name not in SUPPORTED_LOCK_MODELS:
                return self.async_abort(reason="not_sesame")
        except ValueError, KeyError, IndexError:
            return self.async_abort(reason="invalid_mfg_data")

        await self.async_set_unique_id(formatted_mac)
        self._abort_if_unique_id_configured()

        friendly_model = FRIENDLY_MODELS.get(model_name, model_name)
        self.context = {
            **self.context,
            "title_placeholders": {
                "name": f"Sesame {friendly_model} ({mac_address[-5:]})"
            },
        }
        self._mac_address = mac_address
        self._discovery_info = discovery_info
        self._sesame_adv_data = sesame_adv_data

        if not sesame_adv_data.is_registered:
            return await self.async_step_bluetooth_register_confirm()

        return await self.async_step_bluetooth_confirm()

    def _resolve_device_model(self, qr_info: SesameQRCode | None) -> str:
        """Resolve the product model name for the device."""
        if self._sesame_adv_data:
            with contextlib.suppress(ValueError):
                return ProductModels(self._sesame_adv_data.model_id).name

        if qr_info:
            with contextlib.suppress(ValueError):
                return ProductModels(qr_info.model_id).name

        if self._mac_address:
            service_info = async_last_service_info(
                self.hass, self._mac_address, connectable=False
            )
            if not service_info:
                for s_info in async_discovered_service_info(
                    self.hass, connectable=False
                ):
                    if s_info.address == self._mac_address:
                        service_info = s_info
                        break
            if service_info:
                mfg_tuple = get_sesame_mfg_data(
                    service_info.advertisement.manufacturer_data
                )
                if mfg_tuple:
                    _, mfg_data = mfg_tuple
                    with contextlib.suppress(ValueError, KeyError, IndexError):
                        sesame_adv_data = SesameAdData.decode(mfg_data)
                        return ProductModels(sesame_adv_data.model_id).name

        return ProductModels.SESAME5.name

    async def _async_validate_bluetooth_key(
        self, ble_device: BLEDevice, secret_key_hex: str
    ) -> str | None:
        """Validate connection and secret key for a discovered Sesame device."""
        device = SesameDevice(
            ble_device, self._sesame_adv_data, secret_key=secret_key_hex
        )
        try:
            async with asyncio.timeout(15.0):
                await device.connect()
                await device.login()
        except SesameAuthenticationError, SesameKeyError:
            return "invalid_auth"
        except Exception:
            logger.exception("Failed to connect to validate Sesame secret key")
            return "cannot_connect"
        finally:
            with contextlib.suppress(Exception):
                await device.disconnect()
        return None

    async def _async_parse_confirm_secret_key(
        self, user_input: dict[str, Any]
    ) -> tuple[str | None, str | None, SesameQRCode | None, dict[str, str]]:
        """Parse raw secret key or QR code from confirmation step input."""
        errors: dict[str, str] = {}
        raw_secret_key = (user_input.get(CONF_SECRET_KEY) or "").strip()
        qr_code_image = user_input.get("qr_code_image")
        qr_url = (user_input.get(CONF_QR_URL) or "").strip()

        if raw_secret_key.startswith("ssm://"):
            qr_url = raw_secret_key
            raw_secret_key = ""

        qr_info: SesameQRCode | None = None
        if qr_code_image:
            decoded_url = await self.hass.async_add_executor_job(
                _decode_uploaded_qr, self.hass, qr_code_image
            )
            if decoded_url:
                qr_url = decoded_url
            else:
                errors["base"] = "invalid_qr_code"

        secret_key_hex: str | None = None
        if not errors and qr_url:
            try:
                qr_info = SesameQRCode.from_url(qr_url)
                secret_key_hex = qr_info.secret_key.hex()
                if self._sesame_adv_data and (
                    (
                        getattr(qr_info, "device_uuid", None)
                        and getattr(self._sesame_adv_data, "device_uuid", None)
                        and qr_info.device_uuid != self._sesame_adv_data.device_uuid
                    )
                    or (
                        getattr(qr_info, "model_id", None) is not None
                        and getattr(self._sesame_adv_data, "model_id", None) is not None
                        and qr_info.model_id != self._sesame_adv_data.model_id
                    )
                ):
                    errors["base"] = "qr_device_mismatch"
            except Exception as err:  # noqa: BLE001
                logger.debug(
                    "Failed to parse QR code URL in discovery confirm: %s", err
                )
                errors["base"] = "invalid_qr_code"

        if not errors and raw_secret_key and not secret_key_hex:
            if _is_valid_hex_key(raw_secret_key):
                secret_key_hex = raw_secret_key.lower()
            else:
                errors[CONF_SECRET_KEY] = "invalid_secret_key"

        if not errors and not secret_key_hex:
            errors[CONF_SECRET_KEY] = "invalid_secret_key"

        return secret_key_hex, raw_secret_key, qr_info, errors

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovery and request secret key (hex) or QR code for already registered device."""
        errors: dict[str, str] = {}
        assert self._mac_address is not None

        if user_input is None:
            latest_service_info = async_last_service_info(
                self.hass, self._mac_address, connectable=True
            )
            if latest_service_info:
                mfg_tuple = get_sesame_mfg_data(
                    latest_service_info.advertisement.manufacturer_data
                )
                if mfg_tuple:
                    _, mfg_data = mfg_tuple
                    with contextlib.suppress(ValueError, KeyError, IndexError):
                        latest_adv = SesameAdData.decode(mfg_data)
                        if not latest_adv.is_registered:
                            logger.debug(
                                "Device %s was reset to unregistered since discovery; switching to register confirm",
                                self._mac_address,
                            )
                            self._discovery_info = latest_service_info
                            self._sesame_adv_data = latest_adv
                            return await self.async_step_bluetooth_register_confirm()

        if user_input is not None:
            (
                secret_key_hex,
                raw_secret_key,
                qr_info,
                errors,
            ) = await self._async_parse_confirm_secret_key(user_input)

            if not errors and secret_key_hex:
                latest_service_info = async_last_service_info(
                    self.hass, self._mac_address, connectable=True
                )
                if latest_service_info:
                    mfg_tuple = get_sesame_mfg_data(
                        latest_service_info.advertisement.manufacturer_data
                    )
                    if mfg_tuple:
                        with contextlib.suppress(ValueError, KeyError, IndexError):
                            latest_adv = SesameAdData.decode(mfg_tuple[1])
                            if not latest_adv.is_registered:
                                self._discovery_info = latest_service_info
                                self._sesame_adv_data = latest_adv
                                return (
                                    await self.async_step_bluetooth_register_confirm()
                                )

                ble_device = (
                    latest_service_info.device
                    if latest_service_info
                    else (
                        self._discovery_info.device
                        if self._discovery_info
                        else async_ble_device_from_address(
                            self.hass, self._mac_address, connectable=True
                        )
                    )
                )
                if not ble_device:
                    errors["base"] = "device_not_found"
                elif auth_error := await self._async_validate_bluetooth_key(
                    ble_device, secret_key_hex
                ):
                    if auth_error == "invalid_auth" and raw_secret_key:
                        errors[CONF_SECRET_KEY] = auth_error
                    else:
                        errors["base"] = auth_error
                else:
                    model_name = self._resolve_device_model(qr_info)
                    friendly_model = FRIENDLY_MODELS.get(model_name, model_name)
                    title = f"Sesame {friendly_model} ({self._mac_address[-5:]})"
                    if qr_info and qr_info.device_name:
                        title = qr_info.device_name

                    data = {
                        "mac_address": self._mac_address,
                        CONF_SECRET_KEY: secret_key_hex,
                        CONF_MODEL: model_name,
                    }
                    if self._sesame_adv_data:
                        data[CONF_DEVICE_UUID] = str(self._sesame_adv_data.device_uuid)
                    elif qr_info and qr_info.device_uuid:
                        data[CONF_DEVICE_UUID] = str(qr_info.device_uuid)

                    return self.async_create_entry(
                        title=title,
                        data=data,
                    )

        return self.async_show_form(
            step_id="bluetooth_confirm",
            data_schema=probatio.Schema(
                {
                    probatio.Optional(CONF_SECRET_KEY): _PASSWORD_SELECTOR,
                    **(
                        {
                            probatio.Optional("qr_code_image"): selector.FileSelector(
                                selector.FileSelectorConfig(accept="image/*")
                            )
                        }
                        if _FILE_UPLOAD_AVAILABLE and _QRCODE_AVAILABLE
                        else {}
                    ),
                    probatio.Optional(CONF_QR_URL): _PASSWORD_SELECTOR,
                }
            ),
            errors=errors,
        )

    async def async_step_bluetooth_register_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm BLE registration for discovered unregistered Sesame device."""
        errors: dict[str, str] = {}

        if not self._discovery_info or not self._sesame_adv_data:
            return await self.async_step_user()

        assert self._mac_address is not None

        if user_input is None:
            latest_service_info = async_last_service_info(
                self.hass, self._mac_address, connectable=True
            )
            if latest_service_info:
                mfg_tuple = get_sesame_mfg_data(
                    latest_service_info.advertisement.manufacturer_data
                )
                if mfg_tuple:
                    _, mfg_data = mfg_tuple
                    with contextlib.suppress(ValueError, KeyError, IndexError):
                        latest_adv = SesameAdData.decode(mfg_data)
                        if latest_adv.is_registered:
                            logger.debug(
                                "Device %s is already registered in latest broadcast; switching to confirm",
                                self._mac_address,
                            )
                            self._discovery_info = latest_service_info
                            self._sesame_adv_data = latest_adv
                            return await self.async_step_bluetooth_confirm()

        model_name = ProductModels(self._sesame_adv_data.model_id).name
        friendly_model = FRIENDLY_MODELS.get(model_name, model_name)

        if user_input is not None:
            formatted_mac = format_mac(self._mac_address)
            await self.async_set_unique_id(formatted_mac)
            self._abort_if_unique_id_configured()

            latest_service_info = async_last_service_info(
                self.hass, self._mac_address, connectable=True
            )
            if latest_service_info:
                mfg_tuple = get_sesame_mfg_data(
                    latest_service_info.advertisement.manufacturer_data
                )
                if mfg_tuple:
                    _, mfg_data = mfg_tuple
                    with contextlib.suppress(ValueError, KeyError, IndexError):
                        latest_adv = SesameAdData.decode(mfg_data)
                        if latest_adv.is_registered:
                            logger.debug(
                                "Device %s is already registered in latest broadcast; switching to confirm",
                                self._mac_address,
                            )
                            self._discovery_info = latest_service_info
                            self._sesame_adv_data = latest_adv
                            return await self.async_step_bluetooth_confirm()

            ble_device = (
                latest_service_info.device
                if latest_service_info
                else (
                    async_ble_device_from_address(
                        self.hass, self._mac_address, connectable=True
                    )
                    or (self._discovery_info.device if self._discovery_info else None)
                )
            )

            if not ble_device:
                errors["base"] = "device_not_found"
            else:
                device = SesameDevice(ble_device, self._sesame_adv_data)
                try:
                    async with asyncio.timeout(15.0):
                        await device.connect()
                        secret_key_hex = await device.register()
                except Exception:
                    logger.exception("BLE registration failed during auto-discovery")
                    errors["base"] = "registration_failed"
                finally:
                    with contextlib.suppress(Exception):
                        await device.disconnect()

            if not errors:
                assert self._mac_address is not None
                return self.async_create_entry(
                    title=f"Sesame {friendly_model} ({self._mac_address[-5:]})",
                    data={
                        "mac_address": self._mac_address,
                        CONF_SECRET_KEY: secret_key_hex,
                        CONF_MODEL: model_name,
                        CONF_DEVICE_UUID: str(self._sesame_adv_data.device_uuid),
                    },
                )

        self._set_confirm_only()
        return self.async_show_form(
            step_id="bluetooth_register_confirm",
            description_placeholders={
                "model": friendly_model,
                "mac": self._mac_address or "",
            },
            errors=errors,
        )
