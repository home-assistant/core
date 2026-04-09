"""Config flow to configure Heiman."""

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlowResult
from homeassistant.const import CONF_TOKEN
from homeassistant.helpers.config_entry_oauth2_flow import AbstractOAuth2FlowHandler

from .api import HeimanApiClient
from .const import (
    CONF_HOME_ID,
    CONF_USER_ID,
    DOMAIN,
    REQUESTED_SCOPES,
    SCOPES,
)

_LOGGER = logging.getLogger(__name__)


class AuthInfo:
    """Store authentication info temporarily during config flow."""

    def __init__(self):
        """Initialize auth info."""
        self.homes: list[dict[str, Any]] = []
        self.user_info: Any = None
        self.auth_data: dict[str, Any] = {}
        self.selected_home_ids: list[str] = []


class HeimanConfigFlow(AbstractOAuth2FlowHandler, domain=DOMAIN):
    """Handle configuration of Heiman integration."""

    VERSION = 1
    MINOR_VERSION = 2  # Incremented for multi-home support
    DOMAIN = DOMAIN

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._auth_info = AuthInfo()

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @property
    def extra_authorize_data(self) -> dict[str, Any]:
        """Extra data that needs to be appended to the authorize url."""
        return {"scope": " ".join(REQUESTED_SCOPES)}

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Create an entry for Heiman."""
        # 验证 scopes
        if not set(data[CONF_TOKEN].get("scope", "").split()) >= set(SCOPES):
            return self.async_abort(reason="missing_scopes")

        # 创建 API 客户端验证 token 并获取用户信息
        api_client = HeimanApiClient(hass=self.hass, session=None, token_data=data[CONF_TOKEN])

        try:
            user_info = await api_client.async_get_user_info()
        except Exception as err:
            _LOGGER.error("Failed to get user info: %s", err)
            return self.async_abort(reason="token_invalid")

        # 获取家庭信息
        try:
            homes = await api_client.async_get_homes()
            if not homes:
                return self.async_abort(reason="no_homes")
        except Exception as err:
            _LOGGER.error("Failed to get homes: %s", err)
            return self.async_abort(reason="homes_fetch_failed")

        # 存储临时数据用于家庭选择
        self._auth_info.homes = homes if isinstance(homes, list) else []
        self._auth_info.user_info = user_info
        self._auth_info.auth_data = data

        # 进入家庭选择步骤
        return await self.async_step_select_home()

    async def async_step_select_home(
            self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle home selection step with multi-select support."""
        if user_input is not None:
            # 用户选择了家庭（支持多选）
            selected_home_ids = user_input.get(CONF_HOME_ID, [])

            if not selected_home_ids:
                return self.async_show_form(
                    step_id="select_home",
                    data_schema=self._get_home_selection_schema(),
                    errors={"base": "no_home_selected"},
                )

            # 存储选中的家庭 ID
            self._auth_info.selected_home_ids = selected_home_ids

            first_home = next(
                (h for h in self._auth_info.homes if h.home_id == selected_home_ids[0]),
                self._auth_info.homes[0] if self._auth_info.homes else None,
            )

            await self.async_set_unique_id(self._auth_info.user_info.user_id)

            if self.source != SOURCE_REAUTH:
                self._abort_if_unique_id_configured()

                # 构建配置数据
                config_data = {
                    **self._auth_info.auth_data,
                    CONF_HOME_ID: selected_home_ids[0] if selected_home_ids else None,  # 主家庭 ID
                    "home_ids": selected_home_ids,  # 所有选中的家庭 ID
                    CONF_USER_ID: self._auth_info.user_info.user_id,
                }

                # Get title from user info (nick_name or email)
                user_info = self._auth_info.user_info
                title = getattr(user_info, 'nick_name', None) or getattr(user_info, 'email', None) or "Heiman Home"

                return self.async_create_entry(
                    title=title,
                    data=config_data,
                )

            # 处理重新认证
            if (entry := self._get_reauth_entry()) and CONF_TOKEN not in entry.data:
                if entry.data.get(CONF_USER_ID) != self._auth_info.user_info.user_id:
                    return self.async_abort(reason="reauth_user_mismatch")
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(),
                    data_updates={
                        **self._auth_info.auth_data,
                        CONF_HOME_ID: selected_home_ids[0] if selected_home_ids else None,
                        "home_ids": selected_home_ids,
                        CONF_USER_ID: self._auth_info.user_info.user_id,
                    },
                    unique_id=self._auth_info.user_info.user_id,
                )

            self._abort_if_unique_id_mismatch(reason="reauth_account_mismatch")
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(), data_updates=self._auth_info.auth_data
            )

        # Show home selection form
        return self.async_show_form(
            step_id="select_home",
            data_schema=self._get_home_selection_schema(),
            description_placeholders={
                "user_email": self._auth_info.user_info.email or "User",
            },
        )

    def _get_home_selection_schema(self) -> vol.Schema:
        """Get home selection schema with multi-select."""
        homes = self._auth_info.homes

        if not homes:
            return vol.Schema({})

        home_options = {}
        for home in homes:
            home_id = home.home_id
            home_name = home.home_name or "Unknown"
            device_count = home.device_count

            display_text = f"{home_name} [{device_count} devices]"
            home_options[home_id] = display_text

        default_homes = [home.home_id for home in homes if home.home_id]
        
        return vol.Schema(
            {
                vol.Required(CONF_HOME_ID, default=default_homes): cv.multi_select(home_options),
            }
        )

    async def async_step_reauth(
            self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon migration of old entries."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
            self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauth dialog."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
            )
        return await self.async_step_user()

