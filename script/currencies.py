"""Helper script to update currency list from the official source."""
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from .hassfest.serializer import format_python_namespace


def get_currency_list(url):
    """
    Get the currency list from the given URL.

    Returns a set of currency codes.
    """
    req = requests.get(url)
    soup = BeautifulSoup(req.content, "xml")
    currencies = {
        x.Ccy.contents[0]
        for x in soup.ISO_4217.CcyTbl.children
        if (
            x.name == "CcyNtry"
            and x.Ccy
            and x.CcyMnrUnts.contents[0] != "N.A."
            and "IsFund" not in x.CcyNm.attrs
            and x.Ccy.contents[0] != "UYW"
        )
    }
    return currencies


ACTIVE_CURRENCY_URL = "https://www.six-group.com/dam/download/financial-information/data-center/iso-currrency/lists/list-one.xml"
HISTORIC_CURRENCY_URL = "https://www.six-group.com/dam/download/financial-information/data-center/iso-currrency/lists/list-three.xml"

active_currencies = get_currency_list(ACTIVE_CURRENCY_URL)
historic_currencies = get_currency_list(HISTORIC_CURRENCY_URL) - active_currencies

currencies_file_path = Path("homeassistant/generated/currencies.py")
currencies_file_content = format_python_namespace(
    {
        "ACTIVE_CURRENCIES": active_currencies,
        "HISTORIC_CURRENCIES": historic_currencies,
    },
    generator="script.currencies",
)
currencies_file_path.write_text(currencies_file_content)
