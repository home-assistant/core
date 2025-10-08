"""Tests for the Amber config flow."""

from collections.abc import Generator
from datetime import date
from unittest.mock import Mock, patch

from amberelectric import ApiException
from amberelectric.models.site import Site
from amberelectric.models.site_status import SiteStatus
import pytest

from homeassistant.components.amberelectric.config_flow import filter_sites
from homeassistant.components.amberelectric.const import (
    CONF_SITE_ID,
    CONF_SITE_NAME,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

API_KEY = "psk_123456789"

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


@pytest.fixture(name="invalid_key_api")
def mock_invalid_key_api() -> Generator:
    """Return an authentication error."""

    with patch("amberelectric.AmberApi") as mock:
        mock.return_value.get_sites.side_effect = ApiException(status=403)
        yield mock


@pytest.fixture(name="api_error")
def mock_api_error() -> Generator:
    """Return an authentication error."""
    with patch("amberelectric.AmberApi") as mock:
        mock.return_value.get_sites.side_effect = ApiException(status=500)
        yield mock


@pytest.fixture(name="single_site_api")
def mock_single_site_api() -> Generator:
    """Return a single site."""
    site = Site(
        id="01FG0AGP818PXK0DWHXJRRT2DH",
        nmi="11111111111",
        channels=[],
        network="Jemena",
        status=SiteStatus.ACTIVE,
        active_from=date(2002, 1, 1),
        closed_on=None,
        interval_length=30,
    )

    with patch("amberelectric.AmberApi") as mock:
        mock.return_value.get_sites.return_value = [site]
        yield mock


@pytest.fixture(name="single_site_closed_no_close_date_api")
def single_site_closed_no_close_date_api() -> Generator:
    """Return a single closed site with no closed date."""
    site = Site(
        id="01FG0AGP818PXK0DWHXJRRT2DH",
        nmi="11111111111",
        channels=[],
        network="Jemena",
        status=SiteStatus.CLOSED,
        active_from=None,
        closed_on=None,
        interval_length=30,
    )

    with patch("amberelectric.AmberApi") as mock:
        mock.return_value.get_sites.return_value = [site]
        yield mock


@pytest.fixture(name="single_site_pending_api")
def mock_single_site_pending_api() -> Generator:
    """Return a single site."""
    site = Site(
        id="01FG0AGP818PXK0DWHXJRRT2DH",
        nmi="11111111111",
        channels=[],
        network="Jemena",
        status=SiteStatus.PENDING,
        active_from=None,
        closed_on=None,
        interval_length=30,
    )

    with patch("amberelectric.AmberApi") as mock:
        mock.return_value.get_sites.return_value = [site]
        yield mock


@pytest.fixture(name="single_site_rejoin_api")
def mock_single_site_rejoin_api() -> Generator:
    """Return a single site."""
    instance = Mock()
    site_1 = Site(
        id="01HGD9QB72HB3DWQNJ6SSCGXGV",
        nmi="11111111111",
        channels=[],
        network="Jemena",
        status=SiteStatus.CLOSED,
        active_from=date(2002, 1, 1),
        closed_on=date(2002, 6, 1),
        interval_length=30,
    )
    site_2 = Site(
        id="01FG0AGP818PXK0DWHXJRRT2DH",
        nmi="11111111111",
        channels=[],
        network="Jemena",
        status=SiteStatus.ACTIVE,
        active_from=date(2003, 1, 1),
        closed_on=None,
        interval_length=30,
    )
    site_3 = Site(
        id="01FG0AGP818PXK0DWHXJRRT2DH",
        nmi="11111111112",
        channels=[],
        network="Jemena",
        status=SiteStatus.CLOSED,
        active_from=date(2003, 1, 1),
        closed_on=date(2003, 6, 1),
        interval_length=30,
    )
    instance.get_sites.return_value = [site_1, site_2, site_3]

    with patch("amberelectric.AmberApi", return_value=instance):
        yield instance


@pytest.fixture(name="no_site_api")
def mock_no_site_api() -> Generator:
    """Return no site."""
    instance = Mock()
    instance.get_sites.return_value = []

    with patch("amberelectric.AmberApi", return_value=instance):
        yield instance


async def test_single_pending_site(
    hass: HomeAssistant, single_site_pending_api: Mock
) -> None:
    """Test single site."""
    initial_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert initial_result.get("type") is FlowResultType.FORM
    assert initial_result.get("step_id") == "user"

    # Test filling in API key
    enter_api_key_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_API_TOKEN: API_KEY},
    )
    assert enter_api_key_result.get("type") is FlowResultType.FORM
    assert enter_api_key_result.get("step_id") == "site"

    select_site_result = await hass.config_entries.flow.async_configure(
        enter_api_key_result["flow_id"],
        {CONF_SITE_ID: "01FG0AGP818PXK0DWHXJRRT2DH", CONF_SITE_NAME: "Home"},
    )

    # Show available sites
    assert select_site_result.get("type") is FlowResultType.CREATE_ENTRY
    assert select_site_result.get("title") == "Home"
    data = select_site_result.get("data")
    assert data
    assert data[CONF_API_TOKEN] == API_KEY
    assert data[CONF_SITE_ID] == "01FG0AGP818PXK0DWHXJRRT2DH"


async def test_single_site(hass: HomeAssistant, single_site_api: Mock) -> None:
    """Test single site."""
    initial_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert initial_result.get("type") is FlowResultType.FORM
    assert initial_result.get("step_id") == "user"

    # Test filling in API key
    enter_api_key_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_API_TOKEN: API_KEY},
    )
    assert enter_api_key_result.get("type") is FlowResultType.FORM
    assert enter_api_key_result.get("step_id") == "site"

    select_site_result = await hass.config_entries.flow.async_configure(
        enter_api_key_result["flow_id"],
        {CONF_SITE_ID: "01FG0AGP818PXK0DWHXJRRT2DH", CONF_SITE_NAME: "Home"},
    )

    # Show available sites
    assert select_site_result.get("type") is FlowResultType.CREATE_ENTRY
    assert select_site_result.get("title") == "Home"
    data = select_site_result.get("data")
    assert data
    assert data[CONF_API_TOKEN] == API_KEY
    assert data[CONF_SITE_ID] == "01FG0AGP818PXK0DWHXJRRT2DH"


async def test_single_closed_site_no_closed_date(
    hass: HomeAssistant, single_site_closed_no_close_date_api: Mock
) -> None:
    """Test single closed site with no closed date."""
    initial_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert initial_result.get("type") is FlowResultType.FORM
    assert initial_result.get("step_id") == "user"

    # Test filling in API key
    enter_api_key_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_API_TOKEN: API_KEY},
    )
    assert enter_api_key_result.get("type") is FlowResultType.FORM
    assert enter_api_key_result.get("step_id") == "site"

    select_site_result = await hass.config_entries.flow.async_configure(
        enter_api_key_result["flow_id"],
        {CONF_SITE_ID: "01FG0AGP818PXK0DWHXJRRT2DH", CONF_SITE_NAME: "Home"},
    )

    # Show available sites
    assert select_site_result.get("type") is FlowResultType.CREATE_ENTRY
    assert select_site_result.get("title") == "Home"
    data = select_site_result.get("data")
    assert data
    assert data[CONF_API_TOKEN] == API_KEY
    assert data[CONF_SITE_ID] == "01FG0AGP818PXK0DWHXJRRT2DH"


async def test_single_site_rejoin(
    hass: HomeAssistant, single_site_rejoin_api: Mock
) -> None:
    """Test single site."""
    initial_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert initial_result.get("type") is FlowResultType.FORM
    assert initial_result.get("step_id") == "user"

    # Test filling in API key
    enter_api_key_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_API_TOKEN: API_KEY},
    )
    assert enter_api_key_result.get("type") is FlowResultType.FORM
    assert enter_api_key_result.get("step_id") == "site"

    select_site_result = await hass.config_entries.flow.async_configure(
        enter_api_key_result["flow_id"],
        {CONF_SITE_ID: "01FG0AGP818PXK0DWHXJRRT2DH", CONF_SITE_NAME: "Home"},
    )

    # Show available sites
    assert select_site_result.get("type") is FlowResultType.CREATE_ENTRY
    assert select_site_result.get("title") == "Home"
    data = select_site_result.get("data")
    assert data
    assert data[CONF_API_TOKEN] == API_KEY
    assert data[CONF_SITE_ID] == "01FG0AGP818PXK0DWHXJRRT2DH"


async def test_no_site(hass: HomeAssistant, no_site_api: Mock) -> None:
    """Test no site."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_API_TOKEN: "psk_123456789"},
    )

    assert result.get("type") is FlowResultType.FORM
    # Goes back to the user step
    assert result.get("step_id") == "user"
    assert result.get("errors") == {"api_token": "no_site"}


async def test_invalid_key(hass: HomeAssistant, invalid_key_api: Mock) -> None:
    """Test invalid api key."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"

    # Test filling in API key
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_API_TOKEN: "psk_123456789"},
    )
    assert result.get("type") is FlowResultType.FORM
    # Goes back to the user step
    assert result.get("step_id") == "user"
    assert result.get("errors") == {"api_token": "invalid_api_token"}


async def test_unknown_error(hass: HomeAssistant, api_error: Mock) -> None:
    """Test invalid api key."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"

    # Test filling in API key
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_API_TOKEN: "psk_123456789"},
    )
    assert result.get("type") is FlowResultType.FORM
    # Goes back to the user step
    assert result.get("step_id") == "user"
    assert result.get("errors") == {"api_token": "unknown_error"}


async def test_site_deduplication(single_site_rejoin_api: Mock) -> None:
    """Test site deduplication."""
    filtered = filter_sites(single_site_rejoin_api.get_sites())
    assert len(filtered) == 2
    assert (
        next(s for s in filtered if s.nmi == "11111111111").status == SiteStatus.ACTIVE
    )
    assert (
        next(s for s in filtered if s.nmi == "11111111112").status == SiteStatus.CLOSED
    )
