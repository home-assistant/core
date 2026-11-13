"""Config flow for Broadlink Magic Home."""

import asyncio
from typing import Any, override
from urllib.parse import urlencode, urlparse

from broadlink_magic import DiscoveredRMMax, Family
from broadlink_magic.const import RM_MAX_DEVTYPE
import probatio

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.network import NoURLAvailableError, get_url

from .const import DOMAIN, IMPORT_PATH
from .gateway_listener import DATA_GATEWAY_LISTENER, async_get_gateway_listener
from .helpers import family_to_entry_data, gateways_from_entry_data
from .import_session import ImportSession, get_import_manager
from .import_view import async_register_import_view


class BroadlinkMagicHomeFlowHandler(ConfigFlow, domain=DOMAIN):
    """Import a Magic Home family from the BroadLink app."""

    VERSION = 1

    _session: ImportSession | None = None
    _import_task: asyncio.Task[None] | None = None
    _family: Family | None = None
    _gateways: list[DiscoveredRMMax] | None = None
    _existing_entry: ConfigEntry | None = None
    _timeout_shown = False

    @override
    @callback
    def async_remove(self) -> None:
        """Release the import session and the gateway port, however the flow ends."""
        if self._session is not None:
            get_import_manager(self.hass).remove(self._session.project_id)
            self._session = None
        if manager := self.hass.data.get(DATA_GATEWAY_LISTENER):
            self.hass.async_create_task(
                manager.async_release_flow(self.flow_id),
                f"{DOMAIN} release config flow listener",
            )

    def _new_session(self) -> ImportSession:
        """Replace and return the transient import session."""
        if self._session is not None:
            get_import_manager(self.hass).remove(self._session.project_id)
        self._session = get_import_manager(self.hass).create(self.flow_id)
        return self._session

    def _import_url(self, session: ImportSession) -> str:
        """Build the app-compatible one-time family import URL."""
        base_url = get_url(
            self.hass,
            allow_internal=True,
            allow_external=True,
            allow_cloud=False,
            prefer_external=False,
        ).rstrip("/")
        host = urlparse(base_url).hostname or ""
        query = urlencode(
            {
                "projectid": session.project_id,
                "sharetype": "saas_carpark",
                "devaddr": host,
            }
        )
        return f"{base_url}{IMPORT_PATH}?{query}"

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Display a one-time family import QR code."""
        async_register_import_view(self.hass)
        try:
            listener = await async_get_gateway_listener(self.hass)
        except OSError:
            return self.async_abort(reason="cannot_listen")
        listener.acquire_flow(self.flow_id)
        if self._session is None:
            self._new_session()
        assert self._session is not None

        try:
            import_url = self._import_url(self._session)
        except NoURLAvailableError:
            return self.async_abort(reason="no_url")

        if user_input is not None:
            return await self.async_step_wait_for_import()

        return self.async_show_form(
            step_id="user",
            data_schema=probatio.Schema(
                {
                    probatio.Optional("qr"): selector.QrCodeSelector(
                        selector.QrCodeSelectorConfig(
                            data=import_url,
                            scale=5,
                            error_correction_level=selector.QrErrorCorrectionLevel.QUARTILE,
                        )
                    )
                }
            ),
            description_placeholders={"import_url": import_url},
        )

    async def _async_wait_for_import(self) -> None:
        """Wait for the app upload until the import session expires."""
        assert self._session is not None
        async with asyncio.timeout(self._session.remaining):
            await self._session.event.wait()

    async def async_step_wait_for_import(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Wait for the app to upload a family."""
        assert self._session is not None
        if self._import_task is None:
            if self._session.expired and not self._session.event.is_set():
                return await self.async_step_import_timeout()
            self._import_task = self.hass.async_create_task(
                self._async_wait_for_import()
            )

        if not self._import_task.done():
            return self.async_show_progress(
                step_id="wait_for_import",
                progress_action="wait_for_import",
                progress_task=self._import_task,
            )

        try:
            await self._import_task
        except TimeoutError:
            return self.async_show_progress_done(next_step_id="import_timeout")
        finally:
            self._import_task = None
        return self.async_show_progress_done(next_step_id="discover")

    async def async_step_import_timeout(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Allow retrying an expired import."""
        if self._timeout_shown and user_input is not None:
            self._new_session()
            return await self.async_step_user()
        self._timeout_shown = True
        return self.async_show_form(step_id="import_timeout")

    def _gateway_owner(self, family: Family) -> ConfigEntry | None:
        """Return another family entry that owns a gateway of this family."""
        imported_macs = {gateway.mac for gateway in family.gateways if gateway.mac}
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if entry.unique_id == family.family_id:
                continue
            if imported_macs & {
                gateway.mac.lower()
                for gateway in gateways_from_entry_data(dict(entry.data))
            }:
                return entry
        return None

    async def async_step_discover(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Prepare an imported family for confirmation."""
        assert self._session is not None
        families = self._session.families
        if not families:
            return self.async_abort(reason="invalid_import")
        if len(families) != 1:
            return self.async_abort(reason="multiple_families")

        family = families[0]
        if not family.gateways:
            return self.async_abort(reason="no_gateway")
        self._existing_entry = next(
            (
                entry
                for entry in self.hass.config_entries.async_entries(DOMAIN)
                if entry.unique_id == family.family_id
            ),
            None,
        )
        # The latest scan wins; HA aborts the other flows when this one finishes.
        await self.async_set_unique_id(family.family_id, raise_on_progress=False)
        if self._existing_entry is None:
            self._abort_if_unique_id_configured()
        if (owner := self._gateway_owner(family)) is not None:
            return self.async_abort(
                reason="gateway_in_other_family",
                description_placeholders={"family": owner.title},
            )
        self._family = family
        self._gateways = [
            DiscoveredRMMax(
                host="",
                mac=gateway.mac,
                devtype=gateway.devtype or RM_MAX_DEVTYPE,
                name=gateway.name,
                port=0,
            )
            for gateway in family.gateways
        ]
        self.context["title_placeholders"] = {"name": family.name}
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm or reimport the family."""
        assert self._family is not None
        assert self._gateways is not None
        if user_input is not None:
            if (owner := self._gateway_owner(self._family)) is not None:
                return self.async_abort(
                    reason="gateway_in_other_family",
                    description_placeholders={"family": owner.title},
                )
            data = family_to_entry_data(self._family, self._gateways)
            if self._existing_entry is not None:
                for flow in self._async_in_progress(include_uninitialized=True):
                    if flow["flow_id"] != self.flow_id and (
                        flow["context"].get("unique_id") == self.unique_id
                    ):
                        self.hass.config_entries.flow.async_abort(flow["flow_id"])
                return self.async_update_reload_and_abort(
                    self._existing_entry,
                    data=data,
                    title=self._family.name,
                    reason="reconfigure_successful",
                )
            return self.async_create_entry(title=self._family.name, data=data)
        return self.async_show_form(
            step_id="confirm",
            description_placeholders={
                "family_name": self._family.name,
                "gateway_count": str(len(self._gateways)),
                "device_count": str(len(self._family.devices)),
            },
        )
