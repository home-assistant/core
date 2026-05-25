"""Tests for the Mawaqit API wrapper."""

from unittest.mock import AsyncMock, MagicMock, patch

from mawaqit.consts import BadCredentialsException
import pytest

from homeassistant.components.mawaqit import mawaqit_wrapper
from homeassistant.components.mawaqit.types import MawaqitMosqueData


@pytest.fixture
def mock_client() -> MagicMock:
    """Create a mock AsyncMawaqitClient instance."""
    client = MagicMock()
    client.login = AsyncMock()
    client.close = AsyncMock()
    client.get_api_token = AsyncMock(return_value="test-token")
    client.all_mosques_neighborhood = AsyncMock(return_value=[{"uuid": "abc"}])
    client.fetch_mosques_by_keyword = AsyncMock(return_value=[{"uuid": "abc"}])
    client.fetch_prayer_times = AsyncMock(return_value={"calendar": []})
    client.fetch_mosque_by_id = AsyncMock(return_value={"name": "Test"})
    return client


async def test_validate_credentials_success(mock_client: MagicMock) -> None:
    """Test successful credential validation."""
    result = await mawaqit_wrapper.validate_credentials(
        client_instance=mock_client,
    )
    assert result is True
    mock_client.login.assert_called_once()
    mock_client.close.assert_called_once()


async def test_validate_credentials_bad_credentials(mock_client: MagicMock) -> None:
    """Test credential validation with bad credentials."""
    mock_client.login.side_effect = BadCredentialsException
    result = await mawaqit_wrapper.validate_credentials(
        client_instance=mock_client,
    )
    assert result is False
    mock_client.close.assert_called_once()


async def test_validate_credentials_creates_client() -> None:
    """Test that validate_credentials creates a client when none provided."""
    with patch(
        "homeassistant.components.mawaqit.mawaqit_wrapper.AsyncMawaqitClient",
    ) as mock_cls:
        client = mock_cls.return_value
        client.login = AsyncMock()
        client.close = AsyncMock()

        result = await mawaqit_wrapper.validate_credentials(
            username="user", password="pass"
        )
        assert result is True
        mock_cls.assert_called_once_with(username="user", password="pass")
        client.close.assert_called_once()


async def test_get_mawaqit_api_token_success(mock_client: MagicMock) -> None:
    """Test successful API token retrieval."""
    result = await mawaqit_wrapper.get_mawaqit_api_token(
        client_instance=mock_client,
    )
    assert result == "test-token"
    mock_client.close.assert_called_once()


@pytest.mark.parametrize(
    "side_effect",
    [BadCredentialsException, ConnectionError, TimeoutError],
)
async def test_get_mawaqit_api_token_errors_return_none(
    mock_client: MagicMock,
    side_effect: type[Exception],
) -> None:
    """Test that any error during token retrieval returns None."""
    mock_client.get_api_token.side_effect = side_effect
    result = await mawaqit_wrapper.get_mawaqit_api_token(client_instance=mock_client)
    assert result is None
    mock_client.close.assert_called_once()


async def test_get_mawaqit_api_token_creates_client() -> None:
    """Test that get_mawaqit_api_token creates a client when none provided."""
    with patch(
        "homeassistant.components.mawaqit.mawaqit_wrapper.AsyncMawaqitClient",
    ) as mock_cls:
        client = mock_cls.return_value
        client.get_api_token = AsyncMock(return_value="new-token")
        client.close = AsyncMock()

        result = await mawaqit_wrapper.get_mawaqit_api_token(
            username="user", password="pass"
        )
        assert result == "new-token"
        mock_cls.assert_called_once_with(username="user", password="pass")


async def test_all_mosques_neighborhood_success(
    mock_client: MagicMock,
    mock_mosques_search_api_raw: list[dict],
    mock_mosques_search_api_wrapper: list[MawaqitMosqueData],
) -> None:
    """Test successful neighborhood mosque retrieval."""

    mock_client.all_mosques_neighborhood = AsyncMock(
        return_value=mock_mosques_search_api_raw
    )

    result = await mawaqit_wrapper.all_mosques_neighborhood(
        latitude=48.0,
        longitude=2.0,
        client_instance=mock_client,
    )

    assert result == mock_mosques_search_api_wrapper

    mock_client.get_api_token.assert_called_once()
    mock_client.close.assert_called_once()


async def test_all_mosques_neighborhood_creates_client(
    mock_mosques_search_api_raw: list[dict],
    mock_mosques_search_api_wrapper: list[MawaqitMosqueData],
) -> None:
    """Test client creation when none provided."""

    with patch(
        "homeassistant.components.mawaqit.mawaqit_wrapper.AsyncMawaqitClient",
        autospec=True,
    ) as mock_cls:
        client = mock_cls.return_value
        client.get_api_token = AsyncMock()
        client.all_mosques_neighborhood = AsyncMock(
            return_value=mock_mosques_search_api_raw
        )
        client.close = AsyncMock()

        result = await mawaqit_wrapper.all_mosques_neighborhood(
            latitude=48.0,
            longitude=2.0,
            token="tok",
        )

        assert len(result) == len(mock_mosques_search_api_raw)
        assert result == mock_mosques_search_api_wrapper

        mock_cls.assert_called_once()


async def test_all_mosques_by_keyword_success(
    mock_client: MagicMock,
    mock_mosques_search_api_raw: list[dict],
    mock_mosques_search_api_wrapper: list[MawaqitMosqueData],
) -> None:
    """Test successful keyword search."""

    mock_client.fetch_mosques_by_keyword = AsyncMock(
        return_value=mock_mosques_search_api_raw
    )

    result = await mawaqit_wrapper.all_mosques_by_keyword(
        search_keyword="test",
        client_instance=mock_client,
    )

    assert result == mock_mosques_search_api_wrapper

    mock_client.get_api_token.assert_called_once()
    mock_client.close.assert_called_once()


async def test_all_mosques_by_keyword_none_keyword(
    mock_client: MagicMock,
) -> None:
    """Test keyword search with None."""

    result = await mawaqit_wrapper.all_mosques_by_keyword(
        search_keyword=None,
        client_instance=mock_client,
    )

    assert result == []
    mock_client.close.assert_called_once()


async def test_all_mosques_by_keyword_creates_client(
    mock_mosques_search_api_raw: list[dict],
    mock_mosques_search_api_wrapper: list[MawaqitMosqueData],
) -> None:
    """Test client creation for keyword search."""

    with patch(
        "homeassistant.components.mawaqit.mawaqit_wrapper.AsyncMawaqitClient",
        autospec=True,
    ) as mock_cls:
        client = mock_cls.return_value
        client.get_api_token = AsyncMock()
        client.fetch_mosques_by_keyword = AsyncMock(
            return_value=mock_mosques_search_api_raw
        )
        client.close = AsyncMock()

        result = await mawaqit_wrapper.all_mosques_by_keyword(
            search_keyword="test",
            token="tok",
        )

        assert result == mock_mosques_search_api_wrapper

        mock_cls.assert_called_once()


async def test_fetch_prayer_times_success(mock_client: MagicMock) -> None:
    """Test successful prayer times fetch."""
    result = await mawaqit_wrapper.fetch_prayer_times(
        client_instance=mock_client,
    )
    assert result == {"calendar": []}
    mock_client.get_api_token.assert_called_once()
    mock_client.close.assert_called_once()


async def test_fetch_prayer_times_creates_client() -> None:
    """Test that fetch_prayer_times creates a client when none provided."""
    with patch(
        "homeassistant.components.mawaqit.mawaqit_wrapper.AsyncMawaqitClient",
    ) as mock_cls:
        client = mock_cls.return_value
        client.get_api_token = AsyncMock()
        client.fetch_prayer_times = AsyncMock(return_value={"cal": []})
        client.close = AsyncMock()

        result = await mawaqit_wrapper.fetch_prayer_times(mosque="uuid1", token="tok")
        assert result == {"cal": []}
        mock_cls.assert_called_once_with(
            None, None, "uuid1", None, None, "tok", session=None
        )


async def test_fetch_mosque_by_id_success(mock_client: MagicMock) -> None:
    """Test successful mosque fetch by ID."""
    result = await mawaqit_wrapper.fetch_mosque_by_id(
        mosque="uuid1", client_instance=mock_client
    )
    assert result == {"name": "Test"}
    mock_client.get_api_token.assert_called_once()
    mock_client.close.assert_called_once()


async def test_fetch_mosque_by_id_creates_client() -> None:
    """Test that fetch_mosque_by_id creates a client when none provided."""
    with patch(
        "homeassistant.components.mawaqit.mawaqit_wrapper.AsyncMawaqitClient",
    ) as mock_cls:
        client = mock_cls.return_value
        client.get_api_token = AsyncMock()
        client.fetch_mosque_by_id = AsyncMock(return_value={"name": "M"})
        client.close = AsyncMock()

        result = await mawaqit_wrapper.fetch_mosque_by_id(mosque="uuid1", token="tok")
        assert result == {"name": "M"}
        mock_cls.assert_called_once_with(token="tok")
