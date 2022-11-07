"""Helper script to update currency list from the official source."""
import black
from bs4 import BeautifulSoup
import requests

req = requests.get(
    "https://www.six-group.com/dam/download/financial-information/data-center/iso-currrency/lists/list-one.xml"
)
soup = BeautifulSoup(req.content, "xml")
ACTIVE_CURRENCIES = sorted(
    {
        x.Ccy.contents[0]
        for x in soup.ISO_4217.CcyTbl.children
        if x.name == "CcyNtry"
        and x.Ccy
        and x.CcyMnrUnts.contents[0] != "N.A."
        and "IsFund" not in x.CcyNm.attrs
        and x.Ccy.contents[0] != "UYW"
    }
)

req = requests.get(
    "https://www.six-group.com/dam/download/financial-information/data-center/iso-currrency/lists/list-three.xml"
)
soup = BeautifulSoup(req.content, "xml")
HISTORIC_CURRENCIES = sorted(
    {
        x.Ccy.contents[0]
        for x in soup.ISO_4217.HstrcCcyTbl.children
        if x.name == "HstrcCcyNtry"
        and x.Ccy
        and "IsFund" not in x.CcyNm.attrs
        and x.Ccy.contents[0] not in ACTIVE_CURRENCIES
    }
)

print(
    black.format_str(
        "_ACTIVE_CURRENCIES = {" + ",".join(f'"{x}"' for x in ACTIVE_CURRENCIES) + "}",
        mode=black.Mode(),
    )
)
print(
    black.format_str(
        "_HISTORIC_CURRENCIES = {"
        + ",".join(f'"{x}"' for x in HISTORIC_CURRENCIES)
        + "}",
        mode=black.Mode(),
    )
)
