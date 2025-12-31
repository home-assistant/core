"""Test Eufy Security API module."""

import base64
from datetime import UTC, datetime, timedelta
import json as json_module
from unittest.mock import AsyncMock, MagicMock

from aiohttp import ClientError
from eufy_security import (
    Camera,
    CannotConnectError,
    CaptchaRequiredError,
    EufySecurityAPI,
    EufySecurityError,
    InvalidCaptchaError,
    InvalidCredentialsError,
    RequestError,
    Station,
    async_login,
)
from eufy_security.api import (
    SERVER_PUBLIC_KEY,
    decrypt_api_data,
    encrypt_api_data,
    raise_error,
)
import pytest


class TestRaiseOnError:
    """Tests for raise_error helper function."""

    def test_no_error_when_code_zero(self) -> None:
        """Test no error is raised when code is 0."""
        raise_error({"code": 0})  # Should not raise

    def test_no_error_when_code_missing(self) -> None:
        """Test no error is raised when code is missing."""
        raise_error({})  # Should not raise, defaults to 0

    def test_raises_invalid_credentials_for_code_26006(self) -> None:
        """Test InvalidCredentialsError is raised for code 26006."""
        with pytest.raises(InvalidCredentialsError, match="Invalid credentials"):
            raise_error({"code": 26006, "msg": "Invalid credentials"})

    def test_raises_invalid_credentials_for_code_26050(self) -> None:
        """Test InvalidCredentialsError is raised for code 26050 (wrong password)."""
        with pytest.raises(InvalidCredentialsError, match="Wrong password"):
            raise_error({"code": 26050, "msg": "Wrong password"})

    def test_raises_invalid_captcha_for_code_100033(self) -> None:
        """Test InvalidCaptchaError is raised for code 100033."""
        with pytest.raises(InvalidCaptchaError, match="Wrong CAPTCHA"):
            raise_error({"code": 100033, "msg": "Wrong CAPTCHA"})

    def test_raises_eufy_security_error_for_unknown_code(self) -> None:
        """Test EufySecurityError is raised for unknown error codes."""
        with pytest.raises(EufySecurityError, match="Unknown error"):
            raise_error({"code": 99999, "msg": "Unknown error"})

    def test_default_message_for_missing_msg(self) -> None:
        """Test default message when msg is missing."""
        with pytest.raises(EufySecurityError, match="Unknown error \\(code 12345\\)"):
            raise_error({"code": 12345})


class TestEncryptDecryptApiData:
    """Tests for AES encryption/decryption functions."""

    def test_encrypt_decrypt_roundtrip(self) -> None:
        """Test that encrypting then decrypting returns original data."""
        # Use a 32-byte key (AES-256)
        key = b"0123456789abcdef0123456789abcdef"
        original_data = "Hello, World!"

        encrypted = encrypt_api_data(original_data, key)
        decrypted = decrypt_api_data(encrypted, key)

        assert decrypted == original_data

    def test_encrypt_produces_base64(self) -> None:
        """Test that encryption produces base64-encoded output."""
        key = b"0123456789abcdef0123456789abcdef"
        data = "test data"

        encrypted = encrypt_api_data(data, key)

        # Should be valid base64
        base64.b64decode(encrypted)  # Should not raise

    def test_decrypt_handles_null_terminator(self) -> None:
        """Test that decryption properly removes null terminators."""
        key = b"0123456789abcdef0123456789abcdef"
        # Encrypt data with null terminator
        original = "test\x00"
        encrypted = encrypt_api_data(original, key)
        decrypted = decrypt_api_data(encrypted, key)

        # Null terminator should be stripped
        assert decrypted == "test"

    def test_encrypt_decrypt_json_data(self) -> None:
        """Test encryption/decryption with JSON data."""
        key = b"0123456789abcdef0123456789abcdef"
        original = '{"email": "test@example.com", "password": "secret"}'

        encrypted = encrypt_api_data(original, key)
        decrypted = decrypt_api_data(encrypted, key)

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
        camera = Camera(api=api_mock, camera_info=camera_info)

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
        camera = Camera(api=api_mock, camera_info={})

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
        camera = Camera(api=api_mock, camera_info={"ip_addr": ""})

        assert camera.ip_address is None

    def test_camera_update_event_data(
        self, api_mock: MagicMock, camera_info: dict
    ) -> None:
        """Test updating camera with event data."""
        camera = Camera(api=api_mock, camera_info=camera_info)

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
        camera = Camera(api=api_mock, camera_info=camera_info)

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
            api=api_mock,
            camera_info=camera_info,
            rtsp_username="admin",
            rtsp_password="secret123",
        )

        url = await camera.async_start_stream()

        assert url == "rtsp://admin:secret123@192.168.1.100:554/live0"
        # API should not be called for local RTSP
        api_mock.request.assert_not_called()

    @pytest.mark.asyncio
    async def test_camera_start_stream_local_rtsp_url_encodes_credentials(
        self, api_mock: MagicMock, camera_info: dict
    ) -> None:
        """Test that RTSP credentials are URL-encoded."""
        camera = Camera(
            api=api_mock,
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
        api_mock.request = AsyncMock(
            return_value={"data": {"url": "rtsp://cloud.eufy.com/stream"}}
        )

        camera = Camera(api=api_mock, camera_info=camera_info)

        url = await camera.async_start_stream()

        assert url == "rtsp://cloud.eufy.com/stream"
        api_mock.request.assert_called_once()

    @pytest.mark.asyncio
    async def test_camera_start_stream_cloud_failure(
        self, api_mock: MagicMock, camera_info: dict
    ) -> None:
        """Test handling of cloud stream failure."""
        api_mock.request = AsyncMock(side_effect=EufySecurityError("API error"))

        camera = Camera(api=api_mock, camera_info=camera_info)

        url = await camera.async_start_stream()

        assert url is None

    @pytest.mark.asyncio
    async def test_camera_stop_stream(
        self, api_mock: MagicMock, camera_info: dict
    ) -> None:
        """Test stopping camera stream."""
        api_mock.request = AsyncMock()

        camera = Camera(api=api_mock, camera_info=camera_info)

        await camera.async_stop_stream()

        api_mock.request.assert_called_once_with(
            "post",
            "v1/web/equipment/stop_stream",
            json={
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
        api_mock.request = AsyncMock(side_effect=EufySecurityError("API error"))

        camera = Camera(api=api_mock, camera_info=camera_info)

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
            email="test@example.com",
            password="secret",
            websession=session_mock,
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
        api = EufySecurityAPI("test@example.com", "secret", session_mock)

        expiration = datetime.now() + timedelta(days=1)
        api.set_token("my-token", expiration, "https://api.eufy.com")

        assert api.token == "my-token"
        assert api.token_expiration == expiration
        assert api.api_base == "https://api.eufy.com"

    def test_api_get_crypto_state(self, session_mock: MagicMock) -> None:
        """Test getting crypto state for serialization."""
        api = EufySecurityAPI("test@example.com", "secret", session_mock)

        crypto_state = api.get_crypto_state()

        assert "private_key" in crypto_state
        assert "server_public_key" in crypto_state
        # Private key should be hex-encoded DER bytes
        assert len(crypto_state["private_key"]) > 0
        # Server public key is empty initially (set after login)
        assert crypto_state["server_public_key"] == ""

    def test_api_restore_crypto_state_empty_keys(self, session_mock: MagicMock) -> None:
        """Test restore_crypto_state returns False for empty keys."""
        api = EufySecurityAPI("test@example.com", "secret", session_mock)

        assert api.restore_crypto_state("", "") is False
        assert api.restore_crypto_state("abc", "") is False
        assert api.restore_crypto_state("", "abc") is False

    def test_api_restore_crypto_state_invalid_keys(
        self, session_mock: MagicMock
    ) -> None:
        """Test restore_crypto_state returns False for invalid keys."""
        api = EufySecurityAPI("test@example.com", "secret", session_mock)

        # Invalid hex
        assert api.restore_crypto_state("not-hex", "also-not-hex") is False

        # Valid hex but invalid key format
        assert api.restore_crypto_state("abcd", "1234") is False

    def test_api_restore_crypto_state_valid_keys(self, session_mock: MagicMock) -> None:
        """Test restore_crypto_state works with valid keys."""
        api = EufySecurityAPI("test@example.com", "secret", session_mock)

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
        api = EufySecurityAPI("test@example.com", "secret", session_mock)

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

        api = EufySecurityAPI("test@example.com", "secret", session_mock)

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

        api = EufySecurityAPI("test@example.com", "secret", session_mock)

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

        api = EufySecurityAPI("test@example.com", "secret", session_mock)

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

        api = EufySecurityAPI("test@example.com", "secret", session_mock)

        with pytest.raises(CannotConnectError, match="No domain in response"):
            await api._async_get_api_base()

    @pytest.mark.asyncio
    async def test_api_get_api_base_handles_connection_error(
        self, session_mock: MagicMock
    ) -> None:
        """Test that _async_get_api_base handles connection errors."""
        session_mock.get = MagicMock(side_effect=ClientError("Connection failed"))

        api = EufySecurityAPI("test@example.com", "secret", session_mock)

        with pytest.raises(CannotConnectError, match="Connection error"):
            await api._async_get_api_base()

    @pytest.mark.asyncio
    async def test_api_request_success(self, session_mock: MagicMock) -> None:
        """Test successful API request."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json = AsyncMock(return_value={"code": 0, "data": "test"})
        mock_response.raise_for_status = MagicMock()

        session_mock.request = MagicMock(
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response))
        )

        api = EufySecurityAPI("test@example.com", "secret", session_mock)
        api._api_base = "https://api.eufy.com"
        api._token = "test-token"

        result = await api.request("post", "v1/test/endpoint")

        assert result == {"code": 0, "data": "test"}
        session_mock.request.assert_called_once()

    @pytest.mark.asyncio
    async def test_api_request_non_json_response(self, session_mock: MagicMock) -> None:
        """Test handling of non-JSON response."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {"Content-Type": "text/html"}
        mock_response.text = AsyncMock(return_value="<html>Blocked</html>")

        session_mock.request = MagicMock(
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response))
        )

        api = EufySecurityAPI("test@example.com", "secret", session_mock)
        api._api_base = "https://api.eufy.com"

        with pytest.raises(CannotConnectError, match="Unexpected response type"):
            await api.request("post", "v1/test/endpoint")

    @pytest.mark.asyncio
    async def test_api_request_empty_response(self, session_mock: MagicMock) -> None:
        """Test handling of empty response."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json = AsyncMock(return_value=None)
        mock_response.raise_for_status = MagicMock()

        session_mock.request = MagicMock(
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response))
        )

        api = EufySecurityAPI("test@example.com", "secret", session_mock)
        api._api_base = "https://api.eufy.com"

        with pytest.raises(RequestError, match="No response"):
            await api.request("post", "v1/test/endpoint")

    @pytest.mark.asyncio
    async def test_api_request_401_retry(self, session_mock: MagicMock) -> None:
        """Test 401 response triggers re-authentication."""
        # First call returns 401
        error_401 = ClientError("401 Unauthorized")

        # Second call after re-auth succeeds
        success_response = AsyncMock()
        success_response.status = 200
        success_response.headers = {"Content-Type": "application/json"}
        success_response.json = AsyncMock(return_value={"code": 0, "data": "success"})
        success_response.raise_for_status = MagicMock()

        call_count = 0

        def mock_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise error_401
            return AsyncMock(__aenter__=AsyncMock(return_value=success_response))

        session_mock.request = mock_request

        api = EufySecurityAPI("test@example.com", "secret", session_mock)
        api._api_base = "https://api.eufy.com"
        api._token = "test-token"
        # Mock async_authenticate to avoid actual auth
        api.async_authenticate = AsyncMock()

        result = await api.request("post", "v1/test/endpoint")

        assert result == {"code": 0, "data": "success"}
        api.async_authenticate.assert_called_once()

    @pytest.mark.asyncio
    async def test_api_request_connection_error(self, session_mock: MagicMock) -> None:
        """Test handling of connection error."""
        session_mock.request = MagicMock(side_effect=ClientError("Connection refused"))

        api = EufySecurityAPI("test@example.com", "secret", session_mock)
        api._api_base = "https://api.eufy.com"

        with pytest.raises(CannotConnectError, match="Request error"):
            await api.request("post", "v1/test/endpoint")

    @pytest.mark.asyncio
    async def test_api_async_update_device_info(self, session_mock: MagicMock) -> None:
        """Test updating device info."""
        # Mock response for get_devs_list
        devices_response = {
            "code": 0,
            "data": [
                {
                    "device_sn": "T1234567890",
                    "device_name": "Front Door",
                    "device_model": "eufyCam 2",
                }
            ],
        }
        # Mock response for get_hub_list
        hubs_response = {
            "code": 0,
            "data": [
                {
                    "station_sn": "T0987654321",
                    "station_name": "Home Base",
                    "station_model": "HomeBase 2",
                }
            ],
        }
        # Mock response for events
        events_response = {"code": 0, "data": []}

        call_count = 0

        def mock_request_responses(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_resp = AsyncMock()
            mock_resp.status = 200
            mock_resp.headers = {"Content-Type": "application/json"}
            mock_resp.raise_for_status = MagicMock()
            if call_count == 1:
                mock_resp.json = AsyncMock(return_value=devices_response)
            elif call_count == 2:
                mock_resp.json = AsyncMock(return_value=hubs_response)
            else:
                mock_resp.json = AsyncMock(return_value=events_response)
            return AsyncMock(__aenter__=AsyncMock(return_value=mock_resp))

        session_mock.request = mock_request_responses

        api = EufySecurityAPI("test@example.com", "secret", session_mock)
        api._api_base = "https://api.eufy.com"
        api._token = "test-token"

        await api.async_update_device_info()

        assert "T1234567890" in api.cameras
        assert api.cameras["T1234567890"].name == "Front Door"
        assert "T0987654321" in api.stations
        assert api.stations["T0987654321"].name == "Home Base"

    @pytest.mark.asyncio
    async def test_api_async_get_latest_events(self, session_mock: MagicMock) -> None:
        """Test getting latest events."""
        events_response = {
            "code": 0,
            "data": [
                {
                    "device_sn": "T1234567890",
                    "pic_url": "https://example.com/thumb.jpg",
                    "event_time": 1234567890,
                },
                {
                    "device_sn": "T9999999999",
                    "pic_url": "https://example.com/thumb2.jpg",
                    "event_time": 1234567891,
                },
            ],
        }

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json = AsyncMock(return_value=events_response)
        mock_response.raise_for_status = MagicMock()

        session_mock.request = MagicMock(
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response))
        )

        api = EufySecurityAPI("test@example.com", "secret", session_mock)
        api._api_base = "https://api.eufy.com"
        api._token = "test-token"

        result = await api.async_get_latest_events()

        assert "T1234567890" in result
        assert result["T1234567890"]["pic_url"] == "https://example.com/thumb.jpg"
        assert "T9999999999" in result

    @pytest.mark.asyncio
    async def test_api_async_get_latest_events_failure(
        self, session_mock: MagicMock
    ) -> None:
        """Test handling of events API failure."""
        session_mock.request = MagicMock(side_effect=EufySecurityError("API error"))

        api = EufySecurityAPI("test@example.com", "secret", session_mock)
        api._api_base = "https://api.eufy.com"

        result = await api.async_get_latest_events()

        # Should return empty dict on failure
        assert result == {}

    def test_api_decrypt_response_no_key(self, session_mock: MagicMock) -> None:
        """Test _decrypt_response_data raises error when no key available."""
        api = EufySecurityAPI("test@example.com", "secret", session_mock)
        api._response_shared_secret = None

        with pytest.raises(EufySecurityError, match="No decryption key"):
            api._decrypt_response_data("encrypted_data")

    @pytest.mark.asyncio
    async def test_api_async_authenticate_success(
        self, session_mock: MagicMock
    ) -> None:
        """Test successful authentication."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json = AsyncMock(
            return_value={
                "code": 0,
                "data": {
                    "auth_token": "test-token-123",
                    "token_expires_at": 9999999999,
                    "domain": "mysecurity.eufylife.com",
                    "server_secret_info": {
                        "public_key": SERVER_PUBLIC_KEY.hex(),
                    },
                },
            }
        )

        # Mock domain lookup
        domain_response = AsyncMock()
        domain_response.status = 200
        domain_response.json = AsyncMock(
            return_value={"code": 0, "data": {"domain": "mysecurity.eufylife.com"}}
        )

        call_count = 0

        def mock_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return AsyncMock(__aenter__=AsyncMock(return_value=domain_response))
            return AsyncMock(__aenter__=AsyncMock(return_value=mock_response))

        session_mock.get = mock_request
        session_mock.post = MagicMock(
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response))
        )

        api = EufySecurityAPI("test@example.com", "secret", session_mock)

        await api.async_authenticate()

        assert api.token == "test-token-123"
        assert api._api_base == "https://mysecurity.eufylife.com"
        assert api._response_shared_secret is not None

    @pytest.mark.asyncio
    async def test_api_async_authenticate_captcha_required(
        self, session_mock: MagicMock
    ) -> None:
        """Test authentication when CAPTCHA is required."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json = AsyncMock(
            return_value={
                "code": 100032,
                "data": {
                    "captcha_id": "captcha123",
                    "item": "data:image/png;base64,abc",
                },
            }
        )

        # Mock domain lookup
        domain_response = AsyncMock()
        domain_response.status = 200
        domain_response.json = AsyncMock(
            return_value={"code": 0, "data": {"domain": "security.eufylife.com"}}
        )

        session_mock.get = MagicMock(
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=domain_response))
        )
        session_mock.post = MagicMock(
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response))
        )

        api = EufySecurityAPI("test@example.com", "secret", session_mock)

        with pytest.raises(CaptchaRequiredError) as exc_info:
            await api.async_authenticate()

        assert exc_info.value.captcha_id == "captcha123"
        assert exc_info.value.captcha_image == "data:image/png;base64,abc"

    @pytest.mark.asyncio
    async def test_api_async_authenticate_invalid_credentials(
        self, session_mock: MagicMock
    ) -> None:
        """Test authentication with invalid credentials."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json = AsyncMock(
            return_value={
                "code": 26006,
                "msg": "Invalid credentials",
            }
        )

        # Mock domain lookup
        domain_response = AsyncMock()
        domain_response.status = 200
        domain_response.json = AsyncMock(
            return_value={"code": 0, "data": {"domain": "security.eufylife.com"}}
        )

        session_mock.get = MagicMock(
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=domain_response))
        )
        session_mock.post = MagicMock(
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response))
        )

        api = EufySecurityAPI("test@example.com", "secret", session_mock)

        with pytest.raises(InvalidCredentialsError, match="Invalid credentials"):
            await api.async_authenticate()

    @pytest.mark.asyncio
    async def test_api_async_authenticate_no_token(
        self, session_mock: MagicMock
    ) -> None:
        """Test authentication when no token received."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json = AsyncMock(
            return_value={
                "code": 0,
                "data": {},  # No auth_token
            }
        )

        # Mock domain lookup
        domain_response = AsyncMock()
        domain_response.status = 200
        domain_response.json = AsyncMock(
            return_value={"code": 0, "data": {"domain": "security.eufylife.com"}}
        )

        session_mock.get = MagicMock(
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=domain_response))
        )
        session_mock.post = MagicMock(
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response))
        )

        api = EufySecurityAPI("test@example.com", "secret", session_mock)

        with pytest.raises(InvalidCredentialsError, match="No auth token"):
            await api.async_authenticate()

    @pytest.mark.asyncio
    async def test_api_async_authenticate_connection_error(
        self, session_mock: MagicMock
    ) -> None:
        """Test authentication with connection error."""
        # Mock domain lookup
        domain_response = AsyncMock()
        domain_response.status = 200
        domain_response.json = AsyncMock(
            return_value={"code": 0, "data": {"domain": "security.eufylife.com"}}
        )

        session_mock.get = MagicMock(
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=domain_response))
        )
        session_mock.post = MagicMock(side_effect=ClientError("Connection failed"))

        api = EufySecurityAPI("test@example.com", "secret", session_mock)

        with pytest.raises(CannotConnectError, match="Connection error"):
            await api.async_authenticate()

    @pytest.mark.asyncio
    async def test_api_async_authenticate_non_json_response(
        self, session_mock: MagicMock
    ) -> None:
        """Test authentication with non-JSON response."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {"Content-Type": "text/html"}
        mock_response.text = AsyncMock(return_value="<html>Blocked</html>")

        # Mock domain lookup
        domain_response = AsyncMock()
        domain_response.status = 200
        domain_response.json = AsyncMock(
            return_value={"code": 0, "data": {"domain": "security.eufylife.com"}}
        )

        session_mock.get = MagicMock(
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=domain_response))
        )
        session_mock.post = MagicMock(
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response))
        )

        api = EufySecurityAPI("test@example.com", "secret", session_mock)

        with pytest.raises(CannotConnectError, match="Unexpected response type"):
            await api.async_authenticate()

    @pytest.mark.asyncio
    async def test_api_async_authenticate_with_captcha(
        self, session_mock: MagicMock
    ) -> None:
        """Test authentication with CAPTCHA code."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json = AsyncMock(
            return_value={
                "code": 0,
                "data": {
                    "auth_token": "test-token-456",
                    "token_expires_at": 9999999999,
                },
            }
        )

        # Mock domain lookup
        domain_response = AsyncMock()
        domain_response.status = 200
        domain_response.json = AsyncMock(
            return_value={"code": 0, "data": {"domain": "security.eufylife.com"}}
        )

        session_mock.get = MagicMock(
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=domain_response))
        )
        session_mock.post = MagicMock(
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response))
        )

        api = EufySecurityAPI("test@example.com", "secret", session_mock)

        await api.async_authenticate(captcha_id="captcha123", captcha_code="ABC123")

        assert api.token == "test-token-456"
        # Verify the payload included captcha data
        call_args = session_mock.post.call_args
        assert call_args is not None

    @pytest.mark.asyncio
    async def test_api_request_token_expired_refresh(
        self, session_mock: MagicMock
    ) -> None:
        """Test that expired token triggers re-authentication."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json = AsyncMock(return_value={"code": 0, "data": "success"})
        mock_response.raise_for_status = MagicMock()

        session_mock.request = MagicMock(
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response))
        )

        api = EufySecurityAPI("test@example.com", "secret", session_mock)
        api._api_base = "https://api.eufy.com"
        api._token = "old-token"
        # Set expiration to the past (timezone-aware)
        api._token_expiration = datetime(2020, 1, 1, tzinfo=UTC)

        # Mock async_authenticate
        api.async_authenticate = AsyncMock()

        await api.request("post", "v1/test/endpoint")

        # Should have called authenticate due to expired token
        api.async_authenticate.assert_called_once()

    @pytest.mark.asyncio
    async def test_api_async_get_latest_events_encrypted_response(
        self, session_mock: MagicMock
    ) -> None:
        """Test getting latest events with encrypted response."""
        # Create a mock encrypted response
        key = b"0123456789abcdef0123456789abcdef"
        events_data = [
            {"device_sn": "T1234567890", "pic_url": "https://example.com/thumb.jpg"}
        ]
        encrypted = encrypt_api_data(json_module.dumps(events_data), key)

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json = AsyncMock(return_value={"code": 0, "data": encrypted})
        mock_response.raise_for_status = MagicMock()

        session_mock.request = MagicMock(
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response))
        )

        api = EufySecurityAPI("test@example.com", "secret", session_mock)
        api._api_base = "https://api.eufy.com"
        api._token = "test-token"
        api._response_shared_secret = key

        result = await api.async_get_latest_events()

        assert "T1234567890" in result
        assert result["T1234567890"]["pic_url"] == "https://example.com/thumb.jpg"

    @pytest.mark.asyncio
    async def test_api_async_get_latest_events_dict_response(
        self, session_mock: MagicMock
    ) -> None:
        """Test getting latest events with dict response containing data key."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json = AsyncMock(
            return_value={
                "code": 0,
                "data": {
                    "data": [
                        {
                            "device_sn": "T1234567890",
                            "pic_url": "https://example.com/thumb.jpg",
                        }
                    ]
                },
            }
        )
        mock_response.raise_for_status = MagicMock()

        session_mock.request = MagicMock(
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response))
        )

        api = EufySecurityAPI("test@example.com", "secret", session_mock)
        api._api_base = "https://api.eufy.com"
        api._token = "test-token"

        result = await api.async_get_latest_events()

        assert "T1234567890" in result

    @pytest.mark.asyncio
    async def test_api_async_update_device_info_encrypted_response(
        self, session_mock: MagicMock
    ) -> None:
        """Test updating device info with encrypted response."""
        # Create mock encrypted responses
        key = b"0123456789abcdef0123456789abcdef"
        devices_data = [
            {
                "device_sn": "T1234567890",
                "device_name": "Front Door",
                "device_model": "eufyCam 2",
            }
        ]
        stations_data = [
            {
                "station_sn": "T0987654321",
                "station_name": "Home Base",
                "station_model": "HomeBase 2",
            }
        ]
        encrypted_devices = encrypt_api_data(json_module.dumps(devices_data), key)
        encrypted_stations = encrypt_api_data(json_module.dumps(stations_data), key)

        call_count = 0

        def mock_request_responses(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_resp = AsyncMock()
            mock_resp.status = 200
            mock_resp.headers = {"Content-Type": "application/json"}
            mock_resp.raise_for_status = MagicMock()
            if call_count == 1:
                # Devices response (encrypted)
                mock_resp.json = AsyncMock(
                    return_value={"code": 0, "data": encrypted_devices}
                )
            elif call_count == 2:
                # Stations response (encrypted)
                mock_resp.json = AsyncMock(
                    return_value={"code": 0, "data": encrypted_stations}
                )
            else:
                # Events response
                mock_resp.json = AsyncMock(return_value={"code": 0, "data": []})
            return AsyncMock(__aenter__=AsyncMock(return_value=mock_resp))

        session_mock.request = mock_request_responses

        api = EufySecurityAPI("test@example.com", "secret", session_mock)
        api._api_base = "https://api.eufy.com"
        api._token = "test-token"
        api._response_shared_secret = key

        await api.async_update_device_info()

        assert "T1234567890" in api.cameras
        assert api.cameras["T1234567890"].name == "Front Door"
        assert "T0987654321" in api.stations
        assert api.stations["T0987654321"].name == "Home Base"

    @pytest.mark.asyncio
    async def test_api_async_update_device_info_stations_error(
        self, session_mock: MagicMock
    ) -> None:
        """Test updating device info when stations API fails."""
        call_count = 0

        def mock_request_responses(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                # Stations request fails
                raise EufySecurityError("Stations API failed")
            mock_resp = AsyncMock()
            mock_resp.status = 200
            mock_resp.headers = {"Content-Type": "application/json"}
            mock_resp.raise_for_status = MagicMock()
            if call_count == 1:
                mock_resp.json = AsyncMock(
                    return_value={
                        "code": 0,
                        "data": [
                            {
                                "device_sn": "T1234567890",
                                "device_name": "Front Door",
                                "device_model": "eufyCam 2",
                            }
                        ],
                    }
                )
            else:
                mock_resp.json = AsyncMock(return_value={"code": 0, "data": []})
            return AsyncMock(__aenter__=AsyncMock(return_value=mock_resp))

        session_mock.request = mock_request_responses

        api = EufySecurityAPI("test@example.com", "secret", session_mock)
        api._api_base = "https://api.eufy.com"
        api._token = "test-token"

        # Should not raise, just skip stations
        await api.async_update_device_info()

        assert "T1234567890" in api.cameras
        assert len(api.stations) == 0

    @pytest.mark.asyncio
    async def test_api_async_update_existing_camera(
        self, session_mock: MagicMock
    ) -> None:
        """Test updating existing camera info."""
        devices_response = {
            "code": 0,
            "data": [
                {
                    "device_sn": "T1234567890",
                    "device_name": "Updated Name",
                    "device_model": "eufyCam 2",
                }
            ],
        }
        hubs_response = {"code": 0, "data": []}
        events_response = {"code": 0, "data": []}

        call_count = 0

        def mock_request_responses(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_resp = AsyncMock()
            mock_resp.status = 200
            mock_resp.headers = {"Content-Type": "application/json"}
            mock_resp.raise_for_status = MagicMock()
            if call_count == 1:
                mock_resp.json = AsyncMock(return_value=devices_response)
            elif call_count == 2:
                mock_resp.json = AsyncMock(return_value=hubs_response)
            else:
                mock_resp.json = AsyncMock(return_value=events_response)
            return AsyncMock(__aenter__=AsyncMock(return_value=mock_resp))

        session_mock.request = mock_request_responses

        api = EufySecurityAPI("test@example.com", "secret", session_mock)
        api._api_base = "https://api.eufy.com"
        api._token = "test-token"

        # Pre-create camera
        existing_camera = Camera(
            api=api,
            camera_info={
                "device_sn": "T1234567890",
                "device_name": "Old Name",
                "device_model": "eufyCam 2",
            },
        )
        api.cameras["T1234567890"] = existing_camera

        await api.async_update_device_info()

        # Camera should be updated, not replaced
        assert api.cameras["T1234567890"] is existing_camera
        assert api.cameras["T1234567890"].name == "Updated Name"


class TestAsyncLogin:
    """Tests for the async_login function."""

    @pytest.fixture
    def session_mock(self) -> MagicMock:
        """Create a mock aiohttp session."""
        return MagicMock()

    @pytest.mark.asyncio
    async def test_async_login_success(self, session_mock: MagicMock) -> None:
        """Test successful login creates and returns API instance."""
        # Mock domain lookup
        domain_response = AsyncMock()
        domain_response.status = 200
        domain_response.json = AsyncMock(
            return_value={"code": 0, "data": {"domain": "security.eufylife.com"}}
        )

        # Mock login response
        login_response = AsyncMock()
        login_response.status = 200
        login_response.headers = {"Content-Type": "application/json"}
        login_response.json = AsyncMock(
            return_value={
                "code": 0,
                "data": {
                    "auth_token": "test-token",
                    "token_expires_at": 9999999999,
                    "server_secret_info": {"public_key": SERVER_PUBLIC_KEY.hex()},
                },
            }
        )

        # Mock device list response
        devices_response = AsyncMock()
        devices_response.status = 200
        devices_response.headers = {"Content-Type": "application/json"}
        devices_response.json = AsyncMock(
            return_value={
                "code": 0,
                "data": [
                    {
                        "device_sn": "T1234567890",
                        "device_name": "Front Door",
                        "device_model": "eufyCam 2",
                    }
                ],
            }
        )
        devices_response.raise_for_status = MagicMock()

        # Mock stations response
        stations_response = AsyncMock()
        stations_response.status = 200
        stations_response.headers = {"Content-Type": "application/json"}
        stations_response.json = AsyncMock(return_value={"code": 0, "data": []})
        stations_response.raise_for_status = MagicMock()

        # Mock events response
        events_response = AsyncMock()
        events_response.status = 200
        events_response.headers = {"Content-Type": "application/json"}
        events_response.json = AsyncMock(return_value={"code": 0, "data": []})
        events_response.raise_for_status = MagicMock()

        session_mock.get = MagicMock(
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=domain_response))
        )
        session_mock.post = MagicMock(
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=login_response))
        )

        call_count = 0

        def mock_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return AsyncMock(__aenter__=AsyncMock(return_value=devices_response))
            if call_count == 2:
                return AsyncMock(__aenter__=AsyncMock(return_value=stations_response))
            return AsyncMock(__aenter__=AsyncMock(return_value=events_response))

        session_mock.request = mock_request

        api = await async_login(
            email="test@example.com",
            password="secret",
            websession=session_mock,
            country="US",
        )

        assert api is not None
        assert api.token == "test-token"
        assert "T1234567890" in api.cameras

    @pytest.mark.asyncio
    async def test_async_login_captcha_required(self, session_mock: MagicMock) -> None:
        """Test login raises CaptchaRequiredError with API instance."""
        # Mock domain lookup
        domain_response = AsyncMock()
        domain_response.status = 200
        domain_response.json = AsyncMock(
            return_value={"code": 0, "data": {"domain": "security.eufylife.com"}}
        )

        # Mock login response with CAPTCHA required
        login_response = AsyncMock()
        login_response.status = 200
        login_response.headers = {"Content-Type": "application/json"}
        login_response.json = AsyncMock(
            return_value={
                "code": 100032,
                "data": {
                    "captcha_id": "captcha123",
                    "item": "data:image/png;base64,abc",
                },
            }
        )

        session_mock.get = MagicMock(
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=domain_response))
        )
        session_mock.post = MagicMock(
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=login_response))
        )

        with pytest.raises(CaptchaRequiredError) as exc_info:
            await async_login(
                email="test@example.com",
                password="secret",
                websession=session_mock,
            )

        # The error should include the API instance for retry
        assert exc_info.value.api is not None
        assert exc_info.value.captcha_id == "captcha123"
        assert exc_info.value.captcha_image == "data:image/png;base64,abc"

    @pytest.mark.asyncio
    async def test_async_login_reuse_api_instance(
        self, session_mock: MagicMock
    ) -> None:
        """Test login with existing API instance (CAPTCHA retry)."""
        # Create an existing API instance
        existing_api = EufySecurityAPI("test@example.com", "secret", session_mock, "US")
        existing_api._api_base = "https://security.eufylife.com"

        # Mock login response (success with CAPTCHA)
        login_response = AsyncMock()
        login_response.status = 200
        login_response.headers = {"Content-Type": "application/json"}
        login_response.json = AsyncMock(
            return_value={
                "code": 0,
                "data": {
                    "auth_token": "test-token-after-captcha",
                    "token_expires_at": 9999999999,
                    "server_secret_info": {"public_key": SERVER_PUBLIC_KEY.hex()},
                },
            }
        )

        # Mock device list response
        devices_response = AsyncMock()
        devices_response.status = 200
        devices_response.headers = {"Content-Type": "application/json"}
        devices_response.json = AsyncMock(return_value={"code": 0, "data": []})
        devices_response.raise_for_status = MagicMock()

        session_mock.post = MagicMock(
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=login_response))
        )
        session_mock.request = MagicMock(
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=devices_response))
        )

        api = await async_login(
            email="test@example.com",
            password="secret",
            websession=session_mock,
            captcha_id="captcha123",
            captcha_code="ABC123",
            api=existing_api,
        )

        # Should return the same API instance
        assert api is existing_api
        assert api.token == "test-token-after-captcha"

    @pytest.mark.asyncio
    async def test_async_login_invalid_credentials(
        self, session_mock: MagicMock
    ) -> None:
        """Test login with invalid credentials."""
        # Mock domain lookup
        domain_response = AsyncMock()
        domain_response.status = 200
        domain_response.json = AsyncMock(
            return_value={"code": 0, "data": {"domain": "security.eufylife.com"}}
        )

        # Mock login response
        login_response = AsyncMock()
        login_response.status = 200
        login_response.headers = {"Content-Type": "application/json"}
        login_response.json = AsyncMock(
            return_value={
                "code": 26006,
                "msg": "Invalid credentials",
            }
        )

        session_mock.get = MagicMock(
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=domain_response))
        )
        session_mock.post = MagicMock(
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=login_response))
        )

        with pytest.raises(InvalidCredentialsError, match="Invalid credentials"):
            await async_login(
                email="test@example.com",
                password="wrong",
                websession=session_mock,
            )


class TestEdgeCases:
    """Tests for edge cases to improve coverage."""

    @pytest.fixture
    def session_mock(self) -> MagicMock:
        """Create a mock aiohttp session."""
        return MagicMock()

    @pytest.mark.asyncio
    async def test_api_async_get_latest_events_encrypted_null(
        self, session_mock: MagicMock
    ) -> None:
        """Test getting latest events when decrypted response is null."""
        key = b"0123456789abcdef0123456789abcdef"
        # Encrypt null value
        encrypted = encrypt_api_data("null", key)

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json = AsyncMock(return_value={"code": 0, "data": encrypted})
        mock_response.raise_for_status = MagicMock()

        session_mock.request = MagicMock(
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response))
        )

        api = EufySecurityAPI("test@example.com", "secret", session_mock)
        api._api_base = "https://api.eufy.com"
        api._token = "test-token"
        api._response_shared_secret = key

        result = await api.async_get_latest_events()
        assert result == {}

    @pytest.mark.asyncio
    async def test_api_async_get_latest_events_encrypted_dict_with_data(
        self, session_mock: MagicMock
    ) -> None:
        """Test getting latest events when decrypted response is dict with data key."""
        key = b"0123456789abcdef0123456789abcdef"
        # Encrypt dict with data key
        events_data = {
            "data": [
                {"device_sn": "T1234567890", "pic_url": "https://example.com/thumb.jpg"}
            ]
        }
        encrypted = encrypt_api_data(json_module.dumps(events_data), key)

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json = AsyncMock(return_value={"code": 0, "data": encrypted})
        mock_response.raise_for_status = MagicMock()

        session_mock.request = MagicMock(
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response))
        )

        api = EufySecurityAPI("test@example.com", "secret", session_mock)
        api._api_base = "https://api.eufy.com"
        api._token = "test-token"
        api._response_shared_secret = key

        result = await api.async_get_latest_events()
        assert "T1234567890" in result

    @pytest.mark.asyncio
    async def test_api_async_get_latest_events_encrypted_invalid_type(
        self, session_mock: MagicMock
    ) -> None:
        """Test getting latest events when decrypted response is unexpected type."""
        key = b"0123456789abcdef0123456789abcdef"
        # Encrypt just a string (not list/dict/null)
        encrypted = encrypt_api_data('"just a string"', key)

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json = AsyncMock(return_value={"code": 0, "data": encrypted})
        mock_response.raise_for_status = MagicMock()

        session_mock.request = MagicMock(
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response))
        )

        api = EufySecurityAPI("test@example.com", "secret", session_mock)
        api._api_base = "https://api.eufy.com"
        api._token = "test-token"
        api._response_shared_secret = key

        result = await api.async_get_latest_events()
        assert result == {}

    @pytest.mark.asyncio
    async def test_api_async_update_device_info_skip_device_without_sn(
        self, session_mock: MagicMock
    ) -> None:
        """Test that devices without device_sn are skipped."""
        devices_response = {
            "code": 0,
            "data": [
                {
                    # No device_sn
                    "device_name": "Bad Device",
                    "device_model": "Unknown",
                },
                {
                    "device_sn": "T1234567890",
                    "device_name": "Good Device",
                    "device_model": "eufyCam 2",
                },
            ],
        }
        hubs_response = {"code": 0, "data": []}
        events_response = {"code": 0, "data": []}

        call_count = 0

        def mock_request_responses(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_resp = AsyncMock()
            mock_resp.status = 200
            mock_resp.headers = {"Content-Type": "application/json"}
            mock_resp.raise_for_status = MagicMock()
            if call_count == 1:
                mock_resp.json = AsyncMock(return_value=devices_response)
            elif call_count == 2:
                mock_resp.json = AsyncMock(return_value=hubs_response)
            else:
                mock_resp.json = AsyncMock(return_value=events_response)
            return AsyncMock(__aenter__=AsyncMock(return_value=mock_resp))

        session_mock.request = mock_request_responses

        api = EufySecurityAPI("test@example.com", "secret", session_mock)
        api._api_base = "https://api.eufy.com"
        api._token = "test-token"

        await api.async_update_device_info()

        # Only the device with serial should be added
        assert len(api.cameras) == 1
        assert "T1234567890" in api.cameras

    @pytest.mark.asyncio
    async def test_api_async_update_device_info_updates_camera_events(
        self, session_mock: MagicMock
    ) -> None:
        """Test that camera events are updated from latest events."""
        devices_response = {
            "code": 0,
            "data": [
                {
                    "device_sn": "T1234567890",
                    "device_name": "Front Door",
                    "device_model": "eufyCam 2",
                }
            ],
        }
        hubs_response = {"code": 0, "data": []}
        events_response = {
            "code": 0,
            "data": [
                {
                    "device_sn": "T1234567890",
                    "pic_url": "https://example.com/event_thumb.jpg",
                }
            ],
        }

        call_count = 0

        def mock_request_responses(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_resp = AsyncMock()
            mock_resp.status = 200
            mock_resp.headers = {"Content-Type": "application/json"}
            mock_resp.raise_for_status = MagicMock()
            if call_count == 1:
                mock_resp.json = AsyncMock(return_value=devices_response)
            elif call_count == 2:
                mock_resp.json = AsyncMock(return_value=hubs_response)
            else:
                mock_resp.json = AsyncMock(return_value=events_response)
            return AsyncMock(__aenter__=AsyncMock(return_value=mock_resp))

        session_mock.request = mock_request_responses

        api = EufySecurityAPI("test@example.com", "secret", session_mock)
        api._api_base = "https://api.eufy.com"
        api._token = "test-token"

        await api.async_update_device_info()

        # Camera should have event thumbnail
        assert api.cameras["T1234567890"].last_camera_image_url == (
            "https://example.com/event_thumb.jpg"
        )

    @pytest.mark.asyncio
    async def test_api_request_with_custom_headers(
        self, session_mock: MagicMock
    ) -> None:
        """Test API request with custom headers."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json = AsyncMock(return_value={"code": 0, "data": "success"})
        mock_response.raise_for_status = MagicMock()

        session_mock.request = MagicMock(
            return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response))
        )

        api = EufySecurityAPI("test@example.com", "secret", session_mock)
        api._api_base = "https://api.eufy.com"
        api._token = "test-token"

        await api.request(
            "post", "v1/test/endpoint", headers={"Custom-Header": "test-value"}
        )

        # Verify custom header was included
        call_args = session_mock.request.call_args
        assert "Custom-Header" in call_args.kwargs["headers"]
        assert call_args.kwargs["headers"]["Custom-Header"] == "test-value"

    @pytest.mark.asyncio
    async def test_api_request_401_retry_twice_fails(
        self, session_mock: MagicMock
    ) -> None:
        """Test 401 response after retry raises InvalidCredentialsError."""
        # Always return 401
        session_mock.request = MagicMock(side_effect=ClientError("401 Unauthorized"))

        api = EufySecurityAPI("test@example.com", "secret", session_mock)
        api._api_base = "https://api.eufy.com"
        api._token = "test-token"
        api._retry_on_401 = True  # Already retried once
        # Mock async_authenticate to avoid actual auth
        api.async_authenticate = AsyncMock()

        with pytest.raises(InvalidCredentialsError, match="Authentication failed"):
            await api.request("post", "v1/test/endpoint")
