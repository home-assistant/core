"""Helper script to update currency list from the official source."""
from pathlib import Path

from bs4 import BeautifulSoup
import requests

from .hassfest.serializer import format_python_namespace

req = requests.get(
    "https://www.six-group.com/dam/download/financial-information/data-center/iso-currrency/lists/list-one.xml"
)
soup = BeautifulSoup(req.content, "xml")
active_currencies = {
    x.Ccy.contents[0]
    for x in soup.ISO_4217.CcyTbl.children
    if x.name == "CcyNtry"
    and x.Ccy
    and x.CcyMnrUnts.contents[0] != "N.A."
    and "IsFund" not in x.CcyNm.attrs
    and x.Ccy.contents[0] != "UYW"
}

req = requests.get(
    "https://www.six-group.com/dam/download/financial-information/data-center/iso-currrency/lists/list-three.xml"
)
soup = BeautifulSoup(req.content, "xml")
historic_currencies = {
    x.Ccy.contents[0]
    for x in soup.ISO_4217.HstrcCcyTbl.children
    if x.name == "HstrcCcyNtry"
    and x.Ccy
    and "IsFund" not in x.CcyNm.attrs
    and x.Ccy.contents[0] not in active_currencies
}

Path("homeassistant/generated/currencies.py").write_text(
    format_python_namespace(
        {
            "ACTIVE_CURRENCIES": active_currencies,
            "HISTORIC_CURRENCIES": historic_currencies,
        },
        generator="script.currencies",
    )
)
