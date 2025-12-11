"""Test Eufy Security API module."""

import base64
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from aiohttp import ClientError
import pytest

from homeassistant.components.eufy_security.api import (
    SERVER_PUBLIC_KEY,
    Camera,
    CannotConnectError,
    CaptchaRequiredError,
    EufySecurityAPI,
    EufySecurityError,
    InvalidCaptchaError,
    InvalidCredentialsError,
    Station,
    _decrypt_api_data,
    _encrypt_api_data,
    _raise_on_error,
)


class TestRaiseOnError:
    """Tests for _raise_on_error helper function."""

    def test_no_error_when_code_zero(self) -> None:
        """Test no error is raised when code is 0."""
        _raise_on_error({"code": 0})  # Should not raise

    def test_no_error_when_code_missing(self) -> None:
        """Test no error is raised when code is missing."""
        _raise_on_error({})  # Should not raise, defaults to 0

    def test_raises_invalid_credentials_for_code_26006(self) -> None:
        """Test InvalidCredentialsError is raised for code 26006."""
        with pytest.raises(InvalidCredentialsError, match="Invalid credentials"):
            _raise_on_error({"code": 26006, "msg": "Invalid credentials"})

    def test_raises_invalid_credentials_for_code_26050(self) -> None:
        """Test InvalidCredentialsError is raised for code 26050 (wrong password)."""
        with pytest.raises(InvalidCredentialsError, match="Wrong password"):
            _raise_on_error({"code": 26050, "msg": "Wrong password"})

    def test_raises_invalid_captcha_for_code_100033(self) -> None:
        """Test InvalidCaptchaError is raised for code 100033."""
        with pytest.raises(InvalidCaptchaError, match="Wrong CAPTCHA"):
            _raise_on_error({"code": 100033, "msg": "Wrong CAPTCHA"})

    def test_raises_eufy_security_error_for_unknown_code(self) -> None:
        """Test EufySecurityError is raised for unknown error codes."""
        with pytest.raises(EufySecurityError, match="Unknown error"):
            _raise_on_error({"code": 99999, "msg": "Unknown error"})

    def test_default_message_for_missing_msg(self) -> None:
        """Test default message when msg is missing."""
        with pytest.raises(EufySecurityError, match="Unknown error \\(code 12345\\)"):
            _raise_on_error({"code": 12345})


class TestEncryptDecryptApiData:
    """Tests for AES encryption/decryption functions."""

    def test_encrypt_decrypt_roundtrip(self) -> None:
        """Test that encrypting then decrypting returns original data."""
        # Use a 32-byte key (AES-256)
        key = b"0123456789abcdef0123456789abcdef"
        original_data = "Hello, World!"

        encrypted = _encrypt_api_data(original_data, key)
        decrypted = _decrypt_api_data(encrypted, key)

        assert decrypted == original_data

    def test_encrypt_produces_base64(self) -> None:
        """Test that encryption produces base64-encoded output."""
        key = b"0123456789abcdef0123456789abcdef"
        data = "test data"

        encrypted = _encrypt_api_data(data, key)

        # Should be valid base64
        base64.b64decode(encrypted)  # Should not raise

    def test_decrypt_handles_null_terminator(self) -> None:
        """Test that decryption properly removes null terminators."""
        key = b"0123456789abcdef0123456789abcdef"
        # Encrypt data with null terminator
        original = "test\x00"
        encrypted = _encrypt_api_data(original, key)
        decrypted = _decrypt_api_data(encrypted, key)

        # Null terminator should be stripped
        assert decrypted == "test"

    def test_encrypt_decrypt_json_data(self) -> None:
        """Test encryption/decryption with JSON data."""
        key = b"0123456789abcdef0123456789abcdef"
        original = '{"email": "test@example.com", "password": "secret"}'

        encrypted = _encrypt_api_data(original, key)
        decrypted = _decrypt_api_data(encrypted, key)

        assert decrypted == original


class TestCaptchaRequiredError:
    """Tests for CaptchaRequiredError exception."""

    def test_captcha_error_attributes(self) -> None:
        """Test that CaptchaRequiredError stores attributes correctly."""
        api_mock = MagicMock()
        error = CaptchaRequiredError(
            message="CAPTCHA required",
            captcha_id="captcha123",
            captcha_image="data:image/png;base64,abc",
            api=api_mock,
        )

        assert str(error) == "CAPTCHA required"
        assert error.captcha_id == "captcha123"
        assert error.captcha_image == "data:image/png;base64,abc"
        assert error.api is api_mock

    def test_captcha_error_optional_attributes(self) -> None:
        """Test CaptchaRequiredError with optional attributes."""
        error = CaptchaRequiredError(
            message="CAPTCHA needed",
            captcha_id="captcha456",
        )

        assert error.captcha_id == "captcha456"
        assert error.captcha_image is None
        assert error.api is None


class TestCamera:
    """Tests for Camera dataclass."""

    @pytest.fixture
    def api_mock(self) -> MagicMock:
        """Create a mock API instance."""
        return MagicMock()

    @pytest.fixture
    def camera_info(self) -> dict:
        """Create sample camera info."""
        return {
            "device_sn": "T1234567890",
            "device_name": "Front Door",
            "device_model": "eufyCam 2",
            "station_sn": "T0987654321",
            "main_hw_version": "2.2",
            "main_sw_version": "2.0.7.6",
            "ip_addr": "192.168.1.100",
            "cover_path": "https://example.com/thumbnail.jpg",
        }

    def test_camera_properties(self, api_mock: MagicMock, camera_info: dict) -> None:
        """Test Camera property accessors."""
        camera = Camera(_api=api_mock, camera_info=camera_info)

        assert camera.serial == "T1234567890"
        assert camera.name == "Front Door"
        assert camera.model == "eufyCam 2"
        assert camera.station_serial == "T0987654321"
        assert camera.hardware_version == "2.2"
        assert camera.software_version == "2.0.7.6"
        assert camera.ip_address == "192.168.1.100"
        assert camera.last_camera_image_url == "https://example.com/thumbnail.jpg"

    def test_camera_missing_properties(self, api_mock: MagicMock) -> None:
        """Test Camera with missing properties."""
        camera = Camera(_api=api_mock, camera_info={})

        assert camera.serial == ""
        assert camera.name == "Unknown"
        assert camera.model == "Unknown"
        assert camera.station_serial == ""
        assert camera.hardware_version == ""
        assert camera.software_version == ""
        assert camera.ip_address is None
        assert camera.last_camera_image_url is None

    def test_camera_ip_address_empty_string(self, api_mock: MagicMock) -> None:
        """Test Camera returns None for empty IP address."""
        camera = Camera(_api=api_mock, camera_info={"ip_addr": ""})

        assert camera.ip_address is None

    def test_camera_update_event_data(
        self, api_mock: MagicMock, camera_info: dict
    ) -> None:
        """Test updating camera with event data."""
        camera = Camera(_api=api_mock, camera_info=camera_info)

        # Initial thumbnail from camera_info
        assert camera.last_camera_image_url == "https://example.com/thumbnail.jpg"

        # Update with event data
        camera.update_event_data({"pic_url": "https://example.com/event.jpg"})

        # Event data takes precedence
        assert camera.last_camera_image_url == "https://example.com/event.jpg"

    def test_camera_rtsp_credentials(
        self, api_mock: MagicMock, camera_info: dict
    ) -> None:
        """Test Camera RTSP credential storage."""
        camera = Camera(_api=api_mock, camera_info=camera_info)

        assert camera.rtsp_username is None
        assert camera.rtsp_password is None

        camera.rtsp_username = "admin"
        camera.rtsp_password = "secret"

        assert camera.rtsp_username == "admin"
        assert camera.rtsp_password == "secret"

    @pytest.mark.asyncio
    async def test_camera_start_stream_local_rtsp(
        self, api_mock: MagicMock, camera_info: dict
    ) -> None:
        """Test starting stream with local RTSP."""
        camera = Camera(
            _api=api_mock,
            camera_info=camera_info,
            rtsp_username="admin",
            rtsp_password="secret123",
        )

        url = await camera.async_start_stream()

        assert url == "rtsp://admin:secret123@192.168.1.100:554/live0"
        # API should not be called for local RTSP
        api_mock.async_request.assert_not_called()

    @pytest.mark.asyncio
    async def test_camera_start_stream_local_rtsp_url_encodes_credentials(
        self, api_mock: MagicMock, camera_info: dict
    ) -> None:
        """Test that RTSP credentials are URL-encoded."""
        camera = Camera(
            _api=api_mock,
            camera_info=camera_info,
            rtsp_username="user@home",
            rtsp_password="pass:word/test",
        )

        url = await camera.async_start_stream()

        # Special characters should be URL-encoded
        assert "user%40home" in url
        assert "pass%3Aword%2Ftest" in url

    @pytest.mark.asyncio
    async def test_camera_start_stream_cloud_fallback(
        self, api_mock: MagicMock, camera_info: dict
    ) -> None:
        """Test fallback to cloud streaming when no RTSP credentials."""
        api_mock.async_request = AsyncMock(
            return_value={"data": {"url": "rtsp://cloud.eufy.com/stream"}}
        )

        camera = Camera(_api=api_mock, camera_info=camera_info)

        url = await camera.async_start_stream()

        assert url == "rtsp://cloud.eufy.com/stream"
        api_mock.async_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_camera_start_stream_cloud_failure(
        self, api_mock: MagicMock, camera_info: dict
    ) -> None:
        """Test handling of cloud stream failure."""
        api_mock.async_request = AsyncMock(side_effect=EufySecurityError("API error"))

        camera = Camera(_api=api_mock, camera_info=camera_info)

        url = await camera.async_start_stream()

        assert url is None

    @pytest.mark.asyncio
    async def test_camera_stop_stream(
        self, api_mock: MagicMock, camera_info: dict
    ) -> None:
        """Test stopping camera stream."""
        api_mock.async_request = AsyncMock()

        camera = Camera(_api=api_mock, camera_info=camera_info)

        await camera.async_stop_stream()

        api_mock.async_request.assert_called_once_with(
            "post",
            "v1/web/equipment/stop_stream",
            data={
                "device_sn": "T1234567890",
                "station_sn": "T0987654321",
                "proto": 2,
            },
        )

    @pytest.mark.asyncio
    async def test_camera_stop_stream_failure(
        self, api_mock: MagicMock, camera_info: dict
    ) -> None:
        """Test handling of stop stream failure."""
        api_mock.async_request = AsyncMock(side_effect=EufySecurityError("API error"))

        camera = Camera(_api=api_mock, camera_info=camera_info)

        # Should not raise, just log warning
        await camera.async_stop_stream()


class TestStation:
    """Tests for Station dataclass."""

    def test_station_attributes(self) -> None:
        """Test Station dataclass attributes."""
        station = Station(
            serial="T0987654321",
            name="Home Base",
            model="HomeBase 2",
        )

        assert station.serial == "T0987654321"
        assert station.name == "Home Base"
        assert station.model == "HomeBase 2"


class TestEufySecurityAPI:
    """Tests for EufySecurityAPI class."""

    @pytest.fixture
    def session_mock(self) -> MagicMock:
        """Create a mock aiohttp session."""
        return MagicMock()

    def test_api_initialization(self, session_mock: MagicMock) -> None:
        """Test API client initialization."""
        api = EufySecurityAPI(
            session_mock,
            email="test@example.com",
            password="secret",
            country="US",
        )

        assert api._email == "test@example.com"
        assert api._password == "secret"
        assert api._country == "US"
        assert api.token is None
        assert api.token_expiration is None
        assert api.api_base is None
        assert api.cameras == {}
        assert api.stations == {}

    def test_api_set_token(self, session_mock: MagicMock) -> None:
        """Test setting auth token."""
        api = EufySecurityAPI(session_mock, "test@example.com", "secret")

        expiration = datetime.now() + timedelta(days=1)
        api.set_token("my-token", expiration, "https://api.eufy.com")

        assert api.token == "my-token"
        assert api.token_expiration == expiration
        assert api.api_base == "https://api.eufy.com"

    def test_api_get_crypto_state(self, session_mock: MagicMock) -> None:
        """Test getting crypto state for serialization."""
        api = EufySecurityAPI(session_mock, "test@example.com", "secret")

        crypto_state = api.get_crypto_state()

        assert "private_key" in crypto_state
        assert "server_public_key" in crypto_state
        # Private key should be hex-encoded DER bytes
        assert len(crypto_state["private_key"]) > 0
        # Server public key is empty initially (set after login)
        assert crypto_state["server_public_key"] == ""

    def test_api_restore_crypto_state_empty_keys(self, session_mock: MagicMock) -> None:
        """Test restore_crypto_state returns False for empty keys."""
        api = EufySecurityAPI(session_mock, "test@example.com", "secret")

        assert api.restore_crypto_state("", "") is False
        assert api.restore_crypto_state("abc", "") is False
        assert api.restore_crypto_state("", "abc") is False

    def test_api_restore_crypto_state_invalid_keys(
        self, session_mock: MagicMock
    ) -> None:
        """Test restore_crypto_state returns False for invalid keys."""
        api = EufySecurityAPI(session_mock, "test@example.com", "secret")

        # Invalid hex
        assert api.restore_crypto_state("not-hex", "also-not-hex") is False

        # Valid hex but invalid key format
        assert api.restore_crypto_state("abcd", "1234") is False

    def test_api_restore_crypto_state_valid_keys(self, session_mock: MagicMock) -> None:
        """Test restore_crypto_state works with valid keys."""
        api = EufySecurityAPI(session_mock, "test@example.com", "secret")

        # Get the current crypto state
        original_state = api.get_crypto_state()
        private_key_hex = original_state["private_key"]

        # We need a valid server public key - use the hardcoded one
        server_public_key_hex = SERVER_PUBLIC_KEY.hex()

        # Restore with valid keys
        result = api.restore_crypto_state(private_key_hex, server_public_key_hex)

        assert result is True

    @pytest.mark.asyncio
    async def test_api_get_api_base_caches_result(
        self, session_mock: MagicMock
    ) -> None:
        """Test that _async_get_api_base caches the result."""
        api = EufySecurityAPI(session_mock, "test@example.com", "secret")

        # Pre-set the API base
        api._api_base = "https://cached.eufy.com"

        result = await api._async_get_api_base()

        assert result == "https://cached.eufy.com"
        # Session should not be called since we have a cached value
        session_mock.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_api_get_api_base_fetches_domain(
        self, session_mock: MagicMock
    ) -> None:
        """Test that _async_get_api_base fetches domain from server."""
        # Mock the response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={"code": 0, "data": {"domain": "mysecurity.eufylife.com"}}
        )

        session_mock.get = MagicMock(
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response))
        )

        api = EufySecurityAPI(session_mock, "test@example.com", "secret")

        result = await api._async_get_api_base()

        assert result == "https://mysecurity.eufylife.com"
        assert api._api_base == "https://mysecurity.eufylife.com"

    @pytest.mark.asyncio
    async def test_api_get_api_base_handles_error_status(
        self, session_mock: MagicMock
    ) -> None:
        """Test that _async_get_api_base handles non-200 status."""
        mock_response = AsyncMock()
        mock_response.status = 500

        session_mock.get = MagicMock(
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response))
        )

        api = EufySecurityAPI(session_mock, "test@example.com", "secret")

        with pytest.raises(CannotConnectError, match="Failed to get API domain"):
            await api._async_get_api_base()

    @pytest.mark.asyncio
    async def test_api_get_api_base_handles_error_code(
        self, session_mock: MagicMock
    ) -> None:
        """Test that _async_get_api_base handles error code in response."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={"code": 1, "msg": "Error getting domain"}
        )

        session_mock.get = MagicMock(
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response))
        )

        api = EufySecurityAPI(session_mock, "test@example.com", "secret")

        with pytest.raises(CannotConnectError, match="Error getting domain"):
            await api._async_get_api_base()

    @pytest.mark.asyncio
    async def test_api_get_api_base_handles_missing_domain(
        self, session_mock: MagicMock
    ) -> None:
        """Test that _async_get_api_base handles missing domain in response."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"code": 0, "data": {}})

        session_mock.get = MagicMock(
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response))
        )

        api = EufySecurityAPI(session_mock, "test@example.com", "secret")

        with pytest.raises(CannotConnectError, match="No domain in response"):
            await api._async_get_api_base()

    @pytest.mark.asyncio
    async def test_api_get_api_base_handles_connection_error(
        self, session_mock: MagicMock
    ) -> None:
        """Test that _async_get_api_base handles connection errors."""
        session_mock.get = MagicMock(side_effect=ClientError("Connection failed"))

        api = EufySecurityAPI(session_mock, "test@example.com", "secret")

        with pytest.raises(CannotConnectError, match="Connection error"):
            await api._async_get_api_base()
