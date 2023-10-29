"""Helper script to update currency list from the official source."""

from pathlib import Path
from bs4 import BeautifulSoup
import requests

from .hassfest.serializer import format_python_namespace


# Constants for the URLs
ACTIVE_CURRENCIES_URL = "https://www.six-group.com/dam/download/financial-information/data-center/iso-currrency/lists/list-one.xml"
HISTORIC_CURRENCIES_URL = "https://www.six-group.com/dam/download/financial-information/data-center/iso-currrency/lists/list-three.xml"

# Fetch and parse active currencies
try:
    active_req = requests.get(ACTIVE_CURRENCIES_URL)
    active_soup = BeautifulSoup(active_req.content, "xml")
    active_currencies = {
        x.Ccy.contents[0]
        for x in active_soup.ISO_4217.CcyTbl.children
        if x.name == "CcyNtry"
        and x.Ccy
        and x.CcyMnrUnts.contents[0] != "N.A."
        and "IsFund" not in x.CcyNm.attrs
        and x.Ccy.contents[0] != "UYW"
    }
except Exception as e:
    print(f"Error fetching/parsing active currencies: {e}")
    active_currencies = set()

# Fetch and parse historic currencies
try:
    historic_req = requests.get(HISTORIC_CURRENCIES_URL)
    historic_soup = BeautifulSoup(historic_req.content, "xml")
    historic_currencies = {
        x.Ccy.contents[0]
        for x in historic_soup.ISO_4217.HstrcCcyTbl.children
        if x.name == "HstrcCcyNtry"
        and x.Ccy
        and "IsFund" not in x.CcyNm.attrs
        and x.Ccy.contents[0] not in active_currencies
    }
except Exception as e:
    print(f"Error fetching/parsing historic currencies: {e}")
    historic_currencies = set()

# Define the path for writing the Python module
output_path = Path("homeassistant/generated/currencies.py")

# Write the Python module
output_path.write_text(
    format_python_namespace(
        {
            "ACTIVE_CURRENCIES": active_currencies,
            "HISTORIC_CURRENCIES": historic_currencies,
        },
        generator="script.currencies",
    )
)
