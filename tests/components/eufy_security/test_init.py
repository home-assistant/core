"""Test the Eufy Security integration setup."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.eufy_security.api import (
    CannotConnectError,
    CaptchaRequiredError,
    EufySecurityError,
    InvalidCredentialsError,
)
from homeassistant.components.eufy_security.const import (
    CONF_API_BASE,
    CONF_PRIVATE_KEY,
    CONF_SERVER_PUBLIC_KEY,
    CONF_TOKEN,
    CONF_TOKEN_EXPIRATION,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_eufy_api: MagicMock,
) -> None:
    """Test successful setup of a config entry."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_setup_entry_auth_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup fails with invalid credentials."""
    with patch(
        "homeassistant.components.eufy_security.EufySecurityAPI"
    ) as mock_api_class:
        api = MagicMock()
        api.restore_crypto_state = MagicMock(return_value=False)
        api.async_authenticate = AsyncMock(
            side_effect=InvalidCredentialsError("Invalid credentials")
        )
        mock_api_class.return_value = api

        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_entry_cannot_connect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup retries on connection error."""
    with patch(
        "homeassistant.components.eufy_security.EufySecurityAPI"
    ) as mock_api_class:
        api = MagicMock()
        api.restore_crypto_state = MagicMock(return_value=False)
        api.async_authenticate = AsyncMock(
            side_effect=CannotConnectError("Connection failed")
        )
        mock_api_class.return_value = api

        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_api_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup retries on generic API error."""
    with patch(
        "homeassistant.components.eufy_security.EufySecurityAPI"
    ) as mock_api_class:
        api = MagicMock()
        api.restore_crypto_state = MagicMock(return_value=False)
        api.async_authenticate = AsyncMock(side_effect=EufySecurityError("API error"))
        mock_api_class.return_value = api

        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_captcha_required(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup triggers reauth when CAPTCHA is required."""
    with patch(
        "homeassistant.components.eufy_security.EufySecurityAPI"
    ) as mock_api_class:
        api = MagicMock()
        api.restore_crypto_state = MagicMock(return_value=False)
        api.async_authenticate = AsyncMock(
            side_effect=CaptchaRequiredError(
                "CAPTCHA required",
                captcha_id="captcha123",
                captcha_image="data:image/png;base64,ABC",
            )
        )
        mock_api_class.return_value = api

        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # CAPTCHA triggers auth failed -> reauth flow
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_entry_session_restore_success(
    hass: HomeAssistant,
    mock_camera: MagicMock,
    mock_station: MagicMock,
) -> None:
    """Test setup restores session from stored crypto state."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="test@example.com",
        data={
            CONF_EMAIL: "test@example.com",
            CONF_PASSWORD: "test-password",
            CONF_TOKEN: "stored-token",
            CONF_TOKEN_EXPIRATION: (datetime.now() + timedelta(days=1)).isoformat(),
            CONF_API_BASE: "https://mysecurity.eufylife.com",
            CONF_PRIVATE_KEY: "0" * 64,
            CONF_SERVER_PUBLIC_KEY: "0" * 64,
        },
        unique_id="test@example.com",
    )

    with patch(
        "homeassistant.components.eufy_security.EufySecurityAPI"
    ) as mock_api_class:
        api = MagicMock()
        api.cameras = {mock_camera.serial: mock_camera}
        api.stations = {mock_station.serial: mock_station}
        api.restore_crypto_state = MagicMock(return_value=True)
        api.set_token = MagicMock()
        api.async_update_device_info = AsyncMock()
        api.async_authenticate = AsyncMock()
        mock_api_class.return_value = api

        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    # Should have called set_token to restore session
    api.set_token.assert_called_once()
    # Should NOT have called async_authenticate since session was restored
    api.async_authenticate.assert_not_called()


async def test_setup_entry_session_restore_expired_token(
    hass: HomeAssistant,
    mock_camera: MagicMock,
    mock_station: MagicMock,
) -> None:
    """Test setup re-authenticates when token is expired."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="test@example.com",
        data={
            CONF_EMAIL: "test@example.com",
            CONF_PASSWORD: "test-password",
            CONF_TOKEN: "expired-token",
            CONF_TOKEN_EXPIRATION: (datetime.now() - timedelta(days=1)).isoformat(),
            CONF_API_BASE: "https://mysecurity.eufylife.com",
            CONF_PRIVATE_KEY: "0" * 64,
            CONF_SERVER_PUBLIC_KEY: "0" * 64,
        },
        unique_id="test@example.com",
    )

    with patch(
        "homeassistant.components.eufy_security.EufySecurityAPI"
    ) as mock_api_class:
        api = MagicMock()
        api.cameras = {mock_camera.serial: mock_camera}
        api.stations = {mock_station.serial: mock_station}
        api.restore_crypto_state = MagicMock(return_value=True)
        api.async_authenticate = AsyncMock()
        api.async_update_device_info = AsyncMock()
        mock_api_class.return_value = api

        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    # Should have called async_authenticate since token was expired
    api.async_authenticate.assert_called_once()


async def test_setup_entry_session_restore_failed(
    hass: HomeAssistant,
    mock_camera: MagicMock,
    mock_station: MagicMock,
) -> None:
    """Test setup re-authenticates when session restore fails."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="test@example.com",
        data={
            CONF_EMAIL: "test@example.com",
            CONF_PASSWORD: "test-password",
            CONF_TOKEN: "stored-token",
            CONF_TOKEN_EXPIRATION: (datetime.now() + timedelta(days=1)).isoformat(),
            CONF_API_BASE: "https://mysecurity.eufylife.com",
            CONF_PRIVATE_KEY: "invalid",
            CONF_SERVER_PUBLIC_KEY: "invalid",
        },
        unique_id="test@example.com",
    )

    with patch(
        "homeassistant.components.eufy_security.EufySecurityAPI"
    ) as mock_api_class:
        api = MagicMock()
        api.cameras = {mock_camera.serial: mock_camera}
        api.stations = {mock_station.serial: mock_station}
        api.restore_crypto_state = MagicMock(return_value=False)
        api.async_authenticate = AsyncMock()
        api.async_update_device_info = AsyncMock()
        mock_api_class.return_value = api

        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    # Should have called async_authenticate since restore failed
    api.async_authenticate.assert_called_once()


async def test_setup_entry_session_restore_invalid_session(
    hass: HomeAssistant,
    mock_camera: MagicMock,
    mock_station: MagicMock,
) -> None:
    """Test setup re-authenticates when restored session is invalid."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="test@example.com",
        data={
            CONF_EMAIL: "test@example.com",
            CONF_PASSWORD: "test-password",
            CONF_TOKEN: "stored-token",
            CONF_TOKEN_EXPIRATION: (datetime.now() + timedelta(days=1)).isoformat(),
            CONF_API_BASE: "https://mysecurity.eufylife.com",
            CONF_PRIVATE_KEY: "0" * 64,
            CONF_SERVER_PUBLIC_KEY: "0" * 64,
        },
        unique_id="test@example.com",
    )

    with patch(
        "homeassistant.components.eufy_security.EufySecurityAPI"
    ) as mock_api_class:
        api = MagicMock()
        api.cameras = {mock_camera.serial: mock_camera}
        api.stations = {mock_station.serial: mock_station}
        api.restore_crypto_state = MagicMock(return_value=True)
        api.set_token = MagicMock()
        # First update_device_info fails (session invalid), second succeeds,
        # third is from coordinator refresh
        api.async_update_device_info = AsyncMock(
            side_effect=[InvalidCredentialsError("Invalid session"), None, None]
        )
        api.async_authenticate = AsyncMock()
        mock_api_class.return_value = api

        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    # Should have called async_authenticate after session failed
    api.async_authenticate.assert_called_once()


async def test_setup_entry_device_info_auth_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup fails when device info fetch fails with auth error."""
    with patch(
        "homeassistant.components.eufy_security.EufySecurityAPI"
    ) as mock_api_class:
        api = MagicMock()
        api.restore_crypto_state = MagicMock(return_value=False)
        api.async_authenticate = AsyncMock()
        api.async_update_device_info = AsyncMock(
            side_effect=InvalidCredentialsError("Auth failed")
        )
        mock_api_class.return_value = api

        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_entry_device_info_captcha_required(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup fails when device info fetch requires CAPTCHA."""
    with patch(
        "homeassistant.components.eufy_security.EufySecurityAPI"
    ) as mock_api_class:
        api = MagicMock()
        api.restore_crypto_state = MagicMock(return_value=False)
        api.async_authenticate = AsyncMock()
        api.async_update_device_info = AsyncMock(
            side_effect=CaptchaRequiredError(
                "CAPTCHA required", captcha_id="cap", captcha_image="img"
            )
        )
        mock_api_class.return_value = api

        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_entry_device_info_cannot_connect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup retries when device info fetch fails with connection error."""
    with patch(
        "homeassistant.components.eufy_security.EufySecurityAPI"
    ) as mock_api_class:
        api = MagicMock()
        api.restore_crypto_state = MagicMock(return_value=False)
        api.async_authenticate = AsyncMock()
        api.async_update_device_info = AsyncMock(
            side_effect=CannotConnectError("Connection failed")
        )
        mock_api_class.return_value = api

        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_device_info_api_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup retries when device info fetch fails with API error."""
    with patch(
        "homeassistant.components.eufy_security.EufySecurityAPI"
    ) as mock_api_class:
        api = MagicMock()
        api.restore_crypto_state = MagicMock(return_value=False)
        api.async_authenticate = AsyncMock()
        api.async_update_device_info = AsyncMock(
            side_effect=EufySecurityError("API error")
        )
        mock_api_class.return_value = api

        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_with_rtsp_credentials(
    hass: HomeAssistant,
    mock_camera: MagicMock,
    mock_station: MagicMock,
) -> None:
    """Test setup applies RTSP credentials from options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="test@example.com",
        data={
            CONF_EMAIL: "test@example.com",
            CONF_PASSWORD: "test-password",
        },
        options={
            "rtsp_credentials": {
                "T1234567890": {"username": "rtsp_user", "password": "rtsp_pass"}
            }
        },
        unique_id="test@example.com",
    )

    with patch(
        "homeassistant.components.eufy_security.EufySecurityAPI"
    ) as mock_api_class:
        api = MagicMock()
        api.cameras = {mock_camera.serial: mock_camera}
        api.stations = {mock_station.serial: mock_station}
        api.restore_crypto_state = MagicMock(return_value=False)
        api.async_authenticate = AsyncMock()
        api.async_update_device_info = AsyncMock()
        mock_api_class.return_value = api

        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    # Check RTSP credentials were applied
    assert mock_camera.rtsp_username == "rtsp_user"
    assert mock_camera.rtsp_password == "rtsp_pass"


async def test_unload_entry(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test successful unload of a config entry."""
    assert init_integration.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    assert init_integration.state is ConfigEntryState.NOT_LOADED


async def test_options_update_reloads_entry(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test that options update triggers reload."""
    assert init_integration.state is ConfigEntryState.LOADED

    # Update options
    hass.config_entries.async_update_entry(
        init_integration,
        options={
            "rtsp_credentials": {
                "T1234567890": {"username": "new_user", "password": "new_pass"}
            }
        },
    )
    await hass.async_block_till_done()

    # Entry should have been reloaded
    assert init_integration.state is ConfigEntryState.LOADED
