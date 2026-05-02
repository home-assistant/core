"""
WJG Camera Config Flow
======================
Einrichtungsassistent für die HA-Benutzeroberfläche.
Führt durch: IP-Eingabe → Protokoll-Auswahl → Verbindungstest → Speichern
"""
from __future__ import annotations

import logging
import socket
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

from . import (
    CONF_HTTP_RETRIES, CONF_PROTOCOL, CONF_RTSP_PATH, CONF_RTSP_PORT, CONF_SNAPSHOT_PATH,
    DEFAULT_HTTP_PORT, DEFAULT_HTTP_RETRIES, DEFAULT_PASSWORD, DEFAULT_RTSP_PATH, DEFAULT_RTSP_PORT,
    DEFAULT_SNAPSHOT_PATH, DEFAULT_USERNAME, DOMAIN,
    PROTOCOL_HTTP, PROTOCOL_RTSP, PROTOCOL_XM, PROTOCOL_ONVIF,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema({
    vol.Required(CONF_HOST, description={"suggested_value": "192.168.4.1"}): str,
    vol.Optional(CONF_USERNAME, default=DEFAULT_USERNAME): str,
    vol.Optional(CONF_PASSWORD, default=DEFAULT_PASSWORD): str,
    vol.Optional(CONF_PORT, default=DEFAULT_HTTP_PORT): cv.port,
    vol.Optional(CONF_RTSP_PORT, default=DEFAULT_RTSP_PORT): cv.port,
    vol.Optional(CONF_PROTOCOL, default=PROTOCOL_RTSP): vol.In([
        PROTOCOL_RTSP, PROTOCOL_HTTP, PROTOCOL_XM, PROTOCOL_ONVIF
    ]),
    vol.Optional(CONF_HTTP_RETRIES, default=DEFAULT_HTTP_RETRIES): vol.All(
        vol.Coerce(int), vol.Range(min=0, max=5)
    ),
    vol.Optional(CONF_RTSP_PATH, default=DEFAULT_RTSP_PATH): str,
    vol.Optional(CONF_SNAPSHOT_PATH, default=DEFAULT_SNAPSHOT_PATH): str,
})

def _check_host_reachable(host: str, ports: list[int], timeout: float = 3.0) -> int | None:
    """Prüft ob mindestens einer der Ports erreichbar ist. Gibt offenen Port zurück."""
    for port in ports:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return port
        except OSError:
            continue
    return None


# Pyright erkennt den Home-Assistant-Metaclass-Hook fuer `domain=` nicht korrekt.
class WJGCameraConfigFlow(  # pyright: ignore[reportAbstractUsage, reportCallIssue, reportGeneralTypeIssues]
    config_entries.ConfigFlow,
    domain=DOMAIN,
):
    """Config Flow Handler."""

    VERSION = 1

    def __init__(self) -> None:
        """Config-Flow initialisieren."""
        self._host: str | None = None

    def is_matching(self, other_flow: object) -> bool:
        """Flows fuer denselben Host als identisch behandeln."""
        if not isinstance(other_flow, WJGCameraConfigFlow):
            return False
        other_host = getattr(other_flow, "_host", None)
        return self._host is not None and self._host == other_host

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Erstkonfiguration pruefen und Config-Entry anlegen."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = str(user_input[CONF_HOST]).strip()
            self._host = host
            ports: list[int] = [
                int(user_input.get(CONF_PORT, DEFAULT_HTTP_PORT)),
                int(user_input.get(CONF_RTSP_PORT, DEFAULT_RTSP_PORT)),
                34567,
            ]

            # Erreichbarkeit prüfen (in executor weil synchron)
            open_port = await self.hass.async_add_executor_job(
                _check_host_reachable,
                host,
                ports,
                3.0,
            )

            if open_port is None:
                errors["base"] = "cannot_connect"
                _LOGGER.error(
                    "Kamera auf %s nicht erreichbar. "
                    "Ports 80, 554, 34567 alle geschlossen.", host
                )
            else:
                _LOGGER.info(
                    "Kamera gefunden auf %s (Port %s offen)", host, open_port
                )
                await self.async_set_unique_id(f"wjg_{host}")
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"WJG XM-3820 ({host})",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
            description_placeholders={
                "docs_url": "https://github.com/your-repo/wjg-ha-bridge",
                "hotspot_hint": (
                    "Kamera-Hotspot: GW_AP_XXXX • "
                    "Standard-IP im Hotspot-Modus: 192.168.4.1"
                ),
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        """Options-Flow fuer einen bestehenden Config-Entry liefern."""
        return WJGOptionsFlow(config_entry)


class WJGOptionsFlow(config_entries.OptionsFlow):
    """Options Flow für nachträgliche Konfigurationsänderungen."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Optionen fuer einen bestehenden Config-Entry anzeigen oder speichern."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        schema = vol.Schema({
            vol.Optional(
                CONF_RTSP_PATH,
                default=self._config_entry.data.get(CONF_RTSP_PATH, DEFAULT_RTSP_PATH)
            ): str,
            vol.Optional(
                CONF_SNAPSHOT_PATH,
                default=self._config_entry.data.get(CONF_SNAPSHOT_PATH, DEFAULT_SNAPSHOT_PATH)
            ): str,
            vol.Optional(
                CONF_PROTOCOL,
                default=self._config_entry.data.get(CONF_PROTOCOL, PROTOCOL_RTSP)
            ): vol.In([PROTOCOL_RTSP, PROTOCOL_HTTP, PROTOCOL_XM, PROTOCOL_ONVIF]),
            vol.Optional(
                CONF_HTTP_RETRIES,
                default=self._config_entry.options.get(
                    CONF_HTTP_RETRIES,
                    self._config_entry.data.get(CONF_HTTP_RETRIES, DEFAULT_HTTP_RETRIES),
                ),
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=5)),
        })

        return self.async_show_form(step_id="init", data_schema=schema)
