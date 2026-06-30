"""Tests for the Mawaqit API wrapper."""

from unittest.mock import AsyncMock, MagicMock, patch

from mawaqit.exceptions import BadCredentialsException, MawaqitException
import pytest

from homeassistant.components.mawaqit import mawaqit_wrapper
from homeassistant.components.mawaqit.types import MawaqitMosqueData

from .conftest import MOCK_TOKEN

# ---------------------------------------------------------------------------
# Local fixture
# ---------------------------------------------------------------------------
# ``mock_client`` is an injected AsyncMawaqitClient *instance* used via the
# ``client_instance=`` parameter of each wrapper function.  It is deliberately
# kept local to this module because it is not the same as conftest's
# ``mock_mawaqit_client``, which patches the class constructor globally.
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_client() -> MagicMock:
    """Create a mock AsyncMawaqitClient instance."""
    client = MagicMock()
    client.login = AsyncMock()
    client.close = AsyncMock()
    client.get_api_token = AsyncMock(return_value=MOCK_TOKEN)
    client.all_mosques_neighborhood = AsyncMock(return_value=[{"uuid": "abc"}])
    client.fetch_mosques_by_keyword = AsyncMock(return_value=[{"uuid": "abc"}])
    client.fetch_prayer_times = AsyncMock(return_value={"calendar": []})
    client.fetch_mosque_by_id = AsyncMock(return_value={"name": "Test"})
    return client


# ---------------------------------------------------------------------------
# validate_credentials
# ---------------------------------------------------------------------------


async def test_validate_credentials_success(mock_client: MagicMock) -> None:
    """Test successful credential validation."""
    result = await mawaqit_wrapper.validate_credentials(client_instance=mock_client)
    assert result is True
    mock_client.login.assert_called_once()
    mock_client.close.assert_called_once()


async def test_validate_credentials_bad_credentials(mock_client: MagicMock) -> None:
    """Test credential validation with bad credentials."""
    mock_client.login.side_effect = BadCredentialsException
    result = await mawaqit_wrapper.validate_credentials(client_instance=mock_client)
    assert result is False
    mock_client.close.assert_called_once()


async def test_validate_credentials_mawaqit_exception_propagates(
    mock_client: MagicMock,
) -> None:
    """Test MawaqitException propagates from validate_credentials."""
    mock_client.login.side_effect = MawaqitException
    with pytest.raises(MawaqitException):
        await mawaqit_wrapper.validate_credentials(client_instance=mock_client)
    mock_client.close.assert_called_once()


async def test_validate_credentials_creates_client() -> None:
    """Test that validate_credentials creates a client with the injected session."""
    session = MagicMock()
    with patch(
        "homeassistant.components.mawaqit.mawaqit_wrapper.AsyncMawaqitClient",
    ) as mock_cls:
        client = mock_cls.return_value
        client.login = AsyncMock()
        client.close = AsyncMock()

        result = await mawaqit_wrapper.validate_credentials(
            username="user", password="pass", session=session
        )
        assert result is True
        mock_cls.assert_called_once_with(
            username="user", password="pass", session=session
        )
        client.close.assert_called_once()


# ---------------------------------------------------------------------------
# get_mawaqit_api_token
# ---------------------------------------------------------------------------


async def test_get_mawaqit_api_token_success(mock_client: MagicMock) -> None:
    """Test successful API token retrieval."""
    result = await mawaqit_wrapper.get_mawaqit_api_token(client_instance=mock_client)
    assert result == MOCK_TOKEN
    mock_client.close.assert_called_once()


@pytest.mark.parametrize(
    "side_effect",
    [BadCredentialsException, MawaqitException, ConnectionError, TimeoutError],
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
    """Test that get_mawaqit_api_token creates a client with the injected session."""
    session = MagicMock()
    with patch(
        "homeassistant.components.mawaqit.mawaqit_wrapper.AsyncMawaqitClient",
    ) as mock_cls:
        client = mock_cls.return_value
        client.get_api_token = AsyncMock(return_value="new-token")
        client.close = AsyncMock()

        result = await mawaqit_wrapper.get_mawaqit_api_token(
            username="user", password="pass", session=session
        )
        assert result == "new-token"
        mock_cls.assert_called_once_with(
            username="user", password="pass", session=session
        )


# ---------------------------------------------------------------------------
# all_mosques_neighborhood
# ---------------------------------------------------------------------------


async def test_all_mosques_neighborhood_success(
    mock_client: MagicMock,
    mock_mosques_search_api_raw: list[dict],
    mock_mosques_search_api_wrapper: list[MawaqitMosqueData],
) -> None:
    """Test successful neighbourhood mosque retrieval."""
    mock_client.all_mosques_neighborhood = AsyncMock(
        return_value=mock_mosques_search_api_raw
    )
    result = await mawaqit_wrapper.all_mosques_neighborhood(
        latitude=48.0, longitude=2.0, client_instance=mock_client
    )
    assert result == mock_mosques_search_api_wrapper
    mock_client.get_api_token.assert_called_once()
    mock_client.close.assert_called_once()


async def test_all_mosques_neighborhood_creates_client(
    mock_mosques_search_api_raw: list[dict],
    mock_mosques_search_api_wrapper: list[MawaqitMosqueData],
) -> None:
    """Test client creation forwards the injected session."""
    session = MagicMock()
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
            latitude=48.0, longitude=2.0, token=MOCK_TOKEN, session=session
        )
        assert len(result) == len(mock_mosques_search_api_raw)
        assert result == mock_mosques_search_api_wrapper
        assert mock_cls.call_args.kwargs["session"] is session


# ---------------------------------------------------------------------------
# all_mosques_by_keyword
# ---------------------------------------------------------------------------


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
        search_keyword="test", client_instance=mock_client
    )
    assert result == mock_mosques_search_api_wrapper
    mock_client.get_api_token.assert_called_once()
    mock_client.close.assert_called_once()


async def test_all_mosques_by_keyword_none_keyword(mock_client: MagicMock) -> None:
    """Test keyword search with None returns empty list."""
    result = await mawaqit_wrapper.all_mosques_by_keyword(
        search_keyword=None, client_instance=mock_client
    )
    assert result == []
    mock_client.close.assert_called_once()


async def test_all_mosques_by_keyword_creates_client(
    mock_mosques_search_api_raw: list[dict],
    mock_mosques_search_api_wrapper: list[MawaqitMosqueData],
) -> None:
    """Test client creation for keyword search forwards the injected session."""
    session = MagicMock()
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
            search_keyword="test", token=MOCK_TOKEN, session=session
        )
        assert result == mock_mosques_search_api_wrapper
        mock_cls.assert_called_once_with(
            username=None, password=None, token=MOCK_TOKEN, session=session
        )


# ---------------------------------------------------------------------------
# fetch_prayer_times
# ---------------------------------------------------------------------------


async def test_fetch_prayer_times_success(mock_client: MagicMock) -> None:
    """Test successful prayer times fetch."""
    result = await mawaqit_wrapper.fetch_prayer_times(client_instance=mock_client)
    assert result == {"calendar": []}
    mock_client.get_api_token.assert_called_once()
    mock_client.close.assert_called_once()


async def test_fetch_prayer_times_creates_client() -> None:
    """Test that fetch_prayer_times creates a client with the injected session."""
    session = MagicMock()
    with patch(
        "homeassistant.components.mawaqit.mawaqit_wrapper.AsyncMawaqitClient",
    ) as mock_cls:
        client = mock_cls.return_value
        client.get_api_token = AsyncMock()
        client.fetch_prayer_times = AsyncMock(return_value={"cal": []})
        client.close = AsyncMock()

        result = await mawaqit_wrapper.fetch_prayer_times(
            mosque="uuid1", token=MOCK_TOKEN, session=session
        )
        assert result == {"cal": []}
        mock_cls.assert_called_once_with(
            None, None, "uuid1", None, None, MOCK_TOKEN, session=session
        )


# ---------------------------------------------------------------------------
# fetch_mosque_by_id
# ---------------------------------------------------------------------------


async def test_fetch_mosque_by_id_success(mock_client: MagicMock) -> None:
    """Test successful mosque fetch by ID."""
    result = await mawaqit_wrapper.fetch_mosque_by_id(
        mosque="uuid1", client_instance=mock_client
    )
    assert result == {"name": "Test"}
    mock_client.get_api_token.assert_called_once()
    mock_client.close.assert_called_once()


async def test_fetch_mosque_by_id_creates_client() -> None:
    """Test that fetch_mosque_by_id creates a client with the injected session."""
    session = MagicMock()
    with patch(
        "homeassistant.components.mawaqit.mawaqit_wrapper.AsyncMawaqitClient",
    ) as mock_cls:
        client = mock_cls.return_value
        client.get_api_token = AsyncMock()
        client.fetch_mosque_by_id = AsyncMock(return_value={"name": "M"})
        client.close = AsyncMock()

        result = await mawaqit_wrapper.fetch_mosque_by_id(
            mosque="uuid1", token=MOCK_TOKEN, session=session
        )
        assert result == {"name": "M"}
        mock_cls.assert_called_once_with(token=MOCK_TOKEN, session=session)
