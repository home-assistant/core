"""unifiprotect.repairs."""

from __future__ import annotations

from typing import cast

from pyunifiprotect import ProtectApiClient
from pyunifiprotect.data import Bootstrap, Camera, ModelType
from pyunifiprotect.data.types import FirmwareReleaseChannel
import voluptuous as vol

from homeassistant import data_entry_flow
from homeassistant.components.repairs import ConfirmRepairFlow, RepairsFlow
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir

from .const import CONF_ALLOW_EA
from .utils import async_create_api_client


class ProtectRepair(RepairsFlow):
    """Handler for an issue fixing flow."""

    _api: ProtectApiClient
    _entry: ConfigEntry

    def __init__(self, *, api: ProtectApiClient, entry: ConfigEntry) -> None:
        """Create flow."""

        self._api = api
        self._entry = entry
        super().__init__()

    @callback
    def _async_get_placeholders(self) -> dict[str, str]:
        issue_registry = ir.async_get(self.hass)
        description_placeholders = {}
        if issue := issue_registry.async_get_issue(self.handler, self.issue_id):
            description_placeholders = issue.translation_placeholders or {}
            if issue.learn_more_url:
                description_placeholders["learn_more"] = issue.learn_more_url

        return description_placeholders


class EAConfirmRepair(ProtectRepair):
    """Handler for an issue fixing flow."""

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the first step of a fix flow."""

        return await self.async_step_start()

    async def async_step_start(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the confirm step of a fix flow."""
        if user_input is None:
            placeholders = self._async_get_placeholders()
            return self.async_show_form(
                step_id="start",
                data_schema=vol.Schema({}),
                description_placeholders=placeholders,
            )

        nvr = await self._api.get_nvr()
        if nvr.release_channel != FirmwareReleaseChannel.RELEASE:
            return await self.async_step_confirm()
        await self.hass.config_entries.async_reload(self._entry.entry_id)
        return self.async_create_entry(data={})

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the confirm step of a fix flow."""
        if user_input is not None:
            options = dict(self._entry.options)
            options[CONF_ALLOW_EA] = True
            self.hass.config_entries.async_update_entry(self._entry, options=options)
            return self.async_create_entry(data={})

        placeholders = self._async_get_placeholders()
        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),
            description_placeholders=placeholders,
        )


class CloudAccountRepair(ProtectRepair):
    """Handler for an issue fixing flow."""

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the first step of a fix flow."""

        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the first step of a fix flow."""

        if user_input is None:
            placeholders = self._async_get_placeholders()
            return self.async_show_form(
                step_id="confirm",
                data_schema=vol.Schema({}),
                description_placeholders=placeholders,
            )

        self._entry.async_start_reauth(self.hass)
        return self.async_create_entry(data={})


class RTSPRepair(ProtectRepair):
    """Handler for an issue fixing flow."""

    _camera_id: str
    _camera: Camera | None
    _bootstrap: Bootstrap | None

    def __init__(
        self,
        *,
        api: ProtectApiClient,
        entry: ConfigEntry,
        camera_id: str,
    ) -> None:
        """Create flow."""

        super().__init__(api=api, entry=entry)
        self._camera_id = camera_id
        self._bootstrap = None
        self._camera = None

    @callback
    def _async_get_placeholders(self) -> dict[str, str]:
        description_placeholders = super()._async_get_placeholders()
        if self._camera is not None:
            description_placeholders["camera"] = self._camera.display_name

        return description_placeholders

    async def _get_boostrap(self) -> Bootstrap:
        if self._bootstrap is None:
            self._bootstrap = await self._api.get_bootstrap()

        return self._bootstrap

    async def _get_camera(self) -> Camera:
        if self._camera is None:
            bootstrap = await self._get_boostrap()
            self._camera = bootstrap.cameras.get(self._camera_id)
            assert self._camera is not None
        return self._camera

    async def _enable_rtsp(self) -> None:
        camera = await self._get_camera()
        bootstrap = await self._get_boostrap()
        user = bootstrap.users.get(bootstrap.auth_user_id)
        if not user or not camera.can_write(user):
            return

        channel = camera.channels[0]
        channel.is_rtsp_enabled = True
        await self._api.update_device(
            ModelType.CAMERA, camera.id, {"channels": camera.unifi_dict()["channels"]}
        )

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the first step of a fix flow."""

        return await self.async_step_start()

    async def async_step_start(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the first step of a fix flow."""

        if user_input is None:
            # make sure camera object is loaded for placeholders
            await self._get_camera()
            placeholders = self._async_get_placeholders()
            return self.async_show_form(
                step_id="start",
                data_schema=vol.Schema({}),
                description_placeholders=placeholders,
            )

        updated_camera = await self._api.get_camera(self._camera_id)
        if not any(c.is_rtsp_enabled for c in updated_camera.channels):
            await self._enable_rtsp()

        updated_camera = await self._api.get_camera(self._camera_id)
        if any(c.is_rtsp_enabled for c in updated_camera.channels):
            await self.hass.config_entries.async_reload(self._entry.entry_id)
            return self.async_create_entry(data={})
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the confirm step of a fix flow."""
        if user_input is not None:
            return self.async_create_entry(data={})

        placeholders = self._async_get_placeholders()
        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),
            description_placeholders=placeholders,
        )


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create flow."""
    if data is not None and issue_id == "ea_channel_warning":
        entry_id = cast(str, data["entry_id"])
        if (entry := hass.config_entries.async_get_entry(entry_id)) is not None:
            api = async_create_api_client(hass, entry)
            return EAConfirmRepair(api=api, entry=entry)

    elif data is not None and issue_id == "cloud_user":
        entry_id = cast(str, data["entry_id"])
        if (entry := hass.config_entries.async_get_entry(entry_id)) is not None:
            api = async_create_api_client(hass, entry)
            return CloudAccountRepair(api=api, entry=entry)

    elif data is not None and issue_id.startswith("rtsp_disabled_"):
        entry_id = cast(str, data["entry_id"])
        camera_id = cast(str, data["camera_id"])
        if (entry := hass.config_entries.async_get_entry(entry_id)) is not None:
            api = async_create_api_client(hass, entry)
            return RTSPRepair(api=api, entry=entry, camera_id=camera_id)

    return ConfirmRepairFlow()
