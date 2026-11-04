"""Repairs for MQTT."""

from datetime import datetime, timedelta
from functools import partial
from ssl import PROTOCOL_TLS_CLIENT, SSLContext, SSLError
from typing import TYPE_CHECKING, Any

from cryptography.hazmat.primitives.serialization import load_pem_private_key
import probatio

from homeassistant.components.repairs import RepairsFlow, RepairsFlowResult
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, issue_registry as ir
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

from .const import (
    CONF_BROKER,
    CONF_CERTIFICATE_FILE,
    CONF_CLIENT_CERT,
    CONF_CLIENT_CERT_FILE,
    CONF_CLIENT_KEY,
    CONF_CLIENT_KEY_FILE,
    DEFAULT_ENCODING,
    DOMAIN,
)
from .util import certificate_expiry, certificate_file_expiry, get_file_path

URL_MQTT_BROKER_CONFIGURATION = (
    "https://www.home-assistant.io/integrations/mqtt/#broker-configuration"
)

CERTIFICATE_CHECK_INTERVAL = timedelta(days=1)
CERTIFICATE_EXPIRY_WARNING = timedelta(days=30)
ISSUE_CLIENT_CERTIFICATE = "client_certificate"


class MQTTDeviceEntryMigration(RepairsFlow):
    """Handler to remove subentry for migrated MQTT device."""

    def __init__(self, entry_id: str, subentry_id: str, name: str) -> None:
        """Initialize the flow."""
        self.entry_id = entry_id
        self.subentry_id = subentry_id
        self.name = name

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Handle the first step of a fix flow."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Handle the confirm step of a fix flow."""
        if user_input is not None:
            device_registry = dr.async_get(self.hass)
            subentry_device = device_registry.async_get_device_by_identifier(
                (DOMAIN, self.subentry_id), self.entry_id
            )
            entry = self.hass.config_entries.async_get_entry(self.entry_id)
            if TYPE_CHECKING:
                assert entry is not None
                assert subentry_device is not None
            self.hass.config_entries.async_remove_subentry(entry, self.subentry_id)
            return self.async_create_entry(data={})

        return self.async_show_form(
            step_id="confirm",
            data_schema=probatio.Schema({}),
            description_placeholders={"name": self.name},
        )


class MQTTClientCertificateReload(RepairsFlow):
    """Handler to reload MQTT to load a renewed client certificate."""

    def __init__(self, entry_id: str, placeholders: dict[str, str]) -> None:
        """Initialize the flow."""
        self.entry_id = entry_id
        self.placeholders = placeholders

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Handle the first step of a fix flow."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Handle the confirm step of a fix flow."""
        if user_input is not None:
            self.hass.config_entries.async_schedule_reload(self.entry_id)
            return self.async_create_entry(data={})

        return self.async_show_form(
            step_id="confirm",
            data_schema=probatio.Schema({}),
            description_placeholders=self.placeholders,
        )


async def async_setup_client_certificate_check(
    hass: HomeAssistant, entry: ConfigEntry, config: dict[str, Any]
) -> None:
    """Check the expiry of the loaded client certificate on setup and daily."""
    loaded_expiry: datetime | None = None
    if client_cert_file := config.get(CONF_CLIENT_CERT_FILE):
        loaded_expiry = await hass.async_add_executor_job(
            certificate_file_expiry, client_cert_file
        )
    elif client_cert := config.get(CONF_CLIENT_CERT):
        loaded_expiry = certificate_expiry(client_cert.encode(DEFAULT_ENCODING))

    if loaded_expiry is None:
        ir.async_delete_issue(hass, DOMAIN, ISSUE_CLIENT_CERTIFICATE)
        return

    def _check_installed_certificate() -> datetime | tuple[str, dict[str, str]]:
        """Check the installed certificate files.

        Returns the expiry of the installed client certificate,
        or the translation key and placeholders of the problem found.
        """
        if TYPE_CHECKING:
            assert client_cert_file is not None
        if (installed_expiry := certificate_file_expiry(client_cert_file)) is None:
            return "client_certificate_file_invalid", {}
        client_key_file = config.get(CONF_CLIENT_KEY_FILE) or get_file_path(
            CONF_CLIENT_KEY
        )
        if TYPE_CHECKING:
            assert client_key_file is not None
        try:
            with open(client_key_file, "rb") as file:
                load_pem_private_key(file.read(), password=None)
        except OSError, TypeError, ValueError:
            return "client_key_file_invalid", {"client_key_file": client_key_file}
        context = SSLContext(PROTOCOL_TLS_CLIENT)
        try:
            context.load_cert_chain(client_cert_file, client_key_file)
        except SSLError:
            return "client_certificate_key_mismatch", {
                "client_key_file": client_key_file
            }
        if ca_cert_file := config.get(CONF_CERTIFICATE_FILE):
            try:
                context.load_verify_locations(ca_cert_file)
            except OSError:
                return "ca_certificate_file_invalid", {"ca_cert_file": ca_cert_file}
        return installed_expiry

    async def _async_check_client_certificate(now: datetime) -> None:
        """Create or remove the client certificate issue."""
        if loaded_expiry - now > CERTIFICATE_EXPIRY_WARNING:
            ir.async_delete_issue(hass, DOMAIN, ISSUE_CLIENT_CERTIFICATE)
            return

        placeholders = {
            "broker": config[CONF_BROKER],
            "expiry": loaded_expiry.date().isoformat(),
        }
        is_fixable = False
        if not client_cert_file:
            translation_key = "client_certificate_expiring"
        else:
            placeholders["client_cert_file"] = client_cert_file
            result = await hass.async_add_executor_job(_check_installed_certificate)
            if isinstance(result, tuple):
                translation_key, problem_placeholders = result
                placeholders |= problem_placeholders
            elif result > loaded_expiry:
                translation_key = "client_certificate_renewed"
                is_fixable = True
            else:
                translation_key = "client_certificate_file_expiring"

        ir.async_create_issue(
            hass,
            DOMAIN,
            ISSUE_CLIENT_CERTIFICATE,
            config_entry_id=entry.entry_id,
            is_fixable=is_fixable,
            severity=(
                ir.IssueSeverity.ERROR
                if loaded_expiry <= now
                else ir.IssueSeverity.WARNING
            ),
            data={"entry_id": entry.entry_id, **placeholders},
            translation_key=translation_key,
            translation_placeholders=placeholders,
        )

    await _async_check_client_certificate(dt_util.utcnow())
    entry.async_on_unload(
        async_track_time_interval(
            hass, _async_check_client_certificate, CERTIFICATE_CHECK_INTERVAL
        )
    )
    entry.async_on_unload(
        partial(ir.async_delete_issue, hass, DOMAIN, ISSUE_CLIENT_CERTIFICATE)
    )


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create flow."""
    if TYPE_CHECKING:
        assert data is not None
    if issue_id == ISSUE_CLIENT_CERTIFICATE:
        return MQTTClientCertificateReload(
            entry_id=str(data["entry_id"]),
            placeholders={
                key: str(data[key]) for key in ("broker", "expiry", "client_cert_file")
            },
        )
    entry_id: str = data["entry_id"]  # type: ignore[assignment]
    subentry_id: str = data["subentry_id"]  # type: ignore[assignment]
    name: str = data["name"]  # type: ignore[assignment]
    return MQTTDeviceEntryMigration(
        entry_id=entry_id,
        subentry_id=subentry_id,
        name=name,
    )
