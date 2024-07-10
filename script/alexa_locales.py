"""Check if upstream Alexa locales are subset of the core Alexa supported locales."""

from pprint import pprint
import re

from bs4 import BeautifulSoup
import requests

from homeassistant.components.alexa import capabilities

SITE = (
    "https://developer.amazon.com/en-GB/docs/alexa/device-apis/list-of-interfaces.html"
)


def run_script() -> None:
    """Run the script."""
    response = requests.get(SITE, timeout=10)
    soup = BeautifulSoup(response.text, "html.parser")

    table = soup.find("table")
    table_body = table.find_all("tbody")[-1]
    rows = table_body.find_all("tr")
    data = [[ele.text.strip() for ele in row.find_all("td") if ele] for row in rows]
    upstream_locales_raw = {row[0]: row[3] for row in data}
    language_pattern = re.compile(r"^[a-z]{2}-[A-Z]{2}$")
    upstream_locales = {
        upstream_interface: {
            name
            for word in upstream_locale.split(" ")
            if (name := word.strip(",")) and language_pattern.match(name) is not None
        }
        for upstream_interface, upstream_locale in upstream_locales_raw.items()
        if upstream_interface.count(".") == 1  # Skip sub-interfaces
    }

    interfaces_missing = {}
    interfaces_nok = {}
    interfaces_ok = {}

    for upstream_interface, upstream_locale in upstream_locales.items():
        core_interface_name = upstream_interface.replace(".", "")
        core_interface = getattr(capabilities, core_interface_name, None)

        if core_interface is None:
            interfaces_missing[upstream_interface] = upstream_locale
            continue

        core_locale = core_interface.supported_locales

        if not upstream_locale.issubset(core_locale):
            interfaces_nok[core_interface_name] = core_locale
        else:
            interfaces_ok[core_interface_name] = core_locale

    print("Missing interfaces:")
    pprint(list(interfaces_missing))
    print("\n")
    print("Interfaces where upstream locales are not subsets of the core locales:")
    pprint(list(interfaces_nok))
    print("\n")
    print("Interfaces checked ok:")
    pprint(list(interfaces_ok))


if __name__ == "__main__":
    run_script()
