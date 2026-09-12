"""Common fixtures for the ENGIE Belgium tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from aioengiebelgium import (
    AccountRelation,
    AuthFlow,
    BusinessAgreement,
    ConsumptionAddress,
    CustomerAccount,
    CustomerAccountRelations,
    EanPrices,
    PricePeriod,
    PriceSlot,
    PricesResponse,
    ServicePoint,
    bare_ean,
)
import pytest

from homeassistant.components.engie_be.const import (
    CONF_MFA_METHOD,
    CONF_REFRESH_TOKEN,
    DOMAIN,
)
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_USERNAME

from tests.common import MockConfigEntry

USERNAME = "user@example.com"
PASSWORD = "hunter2"
BAN = "000000000001"
BAN_2 = "000000000002"
OFFTAKE_ONLY_EAN = "541448820000000001_ID1"
OFFTAKE_INJECTION_EAN = "541448820000000002_ID1"
_SERVICE_POINT_ENERGY_TYPES = {
    bare_ean(OFFTAKE_ONLY_EAN): "GAS",
    bare_ean(OFFTAKE_INJECTION_EAN): "ELECTRICITY",
}


def _business_agreement(ban: str, *, with_address: bool = True) -> BusinessAgreement:
    """Build a single active business agreement."""
    return BusinessAgreement(
        business_agreement_number=ban,
        active=True,
        consumption_address=ConsumptionAddress(
            street="Main street",
            house_number="1",
            postal_code="1000",
            city="Brussels",
        )
        if with_address
        else None,
    )


def build_relations(*bans: str, with_address: bool = True) -> CustomerAccountRelations:
    """Build a customer-account-relations response with the given active BANs."""
    bans = bans or (BAN,)
    return CustomerAccountRelations(
        accounts=(
            AccountRelation(
                id="account-1",
                admin=True,
                customer_account=CustomerAccount(
                    customer_account_number="can-1",
                    business_agreements=tuple(
                        _business_agreement(ban, with_address=with_address)
                        for ban in bans
                    ),
                ),
            ),
        )
    )


def build_prices(
    *, valid_from: str = "2000-01-01", valid_to: str = "2099-12-31"
) -> PricesResponse:
    """Build a prices response with an offtake-only EAN and a dual-direction EAN."""
    return PricesResponse(
        items=(
            EanPrices(
                ean=OFFTAKE_ONLY_EAN,
                periods=(
                    PricePeriod(
                        valid_from=valid_from,
                        valid_to=valid_to,
                        vat_tariff=6.0,
                        offtake=(
                            PriceSlot(
                                time_of_use_slot_code="TOTAL_HOURS",
                                price_value=0.123456,
                                price_value_excl_vat=0.116468,
                            ),
                        ),
                    ),
                ),
            ),
            EanPrices(
                ean=OFFTAKE_INJECTION_EAN,
                periods=(
                    PricePeriod(
                        valid_from=valid_from,
                        valid_to=valid_to,
                        vat_tariff=6.0,
                        offtake=(
                            PriceSlot(
                                time_of_use_slot_code="S_TOU1_OFFTAKE_PEAK",
                                price_value=0.18,
                                price_value_excl_vat=0.169811,
                            ),
                            PriceSlot(
                                time_of_use_slot_code="EN",
                                price_value=0.12,
                                price_value_excl_vat=0.113208,
                            ),
                            PriceSlot(
                                time_of_use_slot_code="S_TOU1_OFFTAKE_WEEKEND",
                                price_value=0.15,
                                price_value_excl_vat=0.141509,
                            ),
                        ),
                        injection=(
                            PriceSlot(
                                time_of_use_slot_code="S_TOU1_INJECTION_PEAK",
                                price_value=0.05,
                                price_value_excl_vat=0.047170,
                            ),
                        ),
                    ),
                ),
            ),
        )
    )


def build_service_point(ean: str) -> ServicePoint:
    """Build a service point response for a queried (possibly suffixed) EAN."""
    bare = bare_ean(ean)
    return ServicePoint(ean_energy_types={bare: _SERVICE_POINT_ENERGY_TYPES[bare]})


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=USERNAME,
        unique_id=USERNAME.lower(),
        data={
            CONF_USERNAME: USERNAME,
            CONF_MFA_METHOD: "sms",
            CONF_ACCESS_TOKEN: "access-token",
            CONF_REFRESH_TOKEN: "refresh-token",
        },
    )


@pytest.fixture
def mock_engie_client() -> Generator[MagicMock]:
    """Mock the EngieBeClient class constructed during config entry setup."""
    with patch(
        "homeassistant.components.engie_be.EngieBeClient", autospec=True
    ) as mock_client_class:
        client = mock_client_class.return_value
        client.async_get_customer_account_relations.return_value = build_relations()
        client.async_get_prices.return_value = build_prices()
        client.async_get_service_point.side_effect = build_service_point
        yield mock_client_class


@pytest.fixture
def mock_auth_flow() -> MagicMock:
    """Return a mock in-progress authentication flow."""
    auth_flow = MagicMock(spec=AuthFlow)
    auth_flow.async_submit_mfa = AsyncMock(
        return_value=("new-access-token", "new-refresh-token")
    )
    return auth_flow


@pytest.fixture
def mock_config_flow_client(mock_auth_flow: MagicMock) -> Generator[MagicMock]:
    """Mock the EngieBeClient constructed by the config flow."""
    with patch(
        "homeassistant.components.engie_be.config_flow.EngieBeClient", autospec=True
    ) as mock_client_class:
        client = mock_client_class.return_value
        client.async_start_authentication.return_value = mock_auth_flow
        yield client


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.engie_be.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry
