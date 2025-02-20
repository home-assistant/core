"""Check if upstream Alexa locales are subset of the core Alexa supported locales."""

import re
import logging
import concurrent.futures

import requests
from bs4 import BeautifulSoup

from homeassistant.components.alexa import capabilities

SITE = "https://developer.amazon.com/en-GB/docs/alexa/device-apis/list-of-interfaces.html"
TIMEOUT = 10
MAX_WORKERS = 5

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def fetch_data(url: str, timeout: int) -> str:
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
        return response.text
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching data from {url}: {e}")
        raise


def parse_html(html: str) -> list[list[str]]:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if not table:
        raise ValueError("Table not found in HTML.")

    table_body = table.find_all("tbody")[-1]
    rows = table_body.find_all("tr")
    return [[ele.text.strip() for ele in row.find_all("td") if ele] for row in rows]


def extract_locales(data: list[list[str]]) -> dict[str, set[str]]:
    upstream_locales_raw = {row[0]: row[3] for row in data if len(row) > 3}
    language_pattern = re.compile(r"^[a-z]{2}-[A-Z]{2}$")
    return {
        upstream_interface: {
            name
            for word in upstream_locale.split(" ")
            if (name := word.strip(",")) and language_pattern.match(name) is not None
        }
        for upstream_interface, upstream_locale in upstream_locales_raw.items()
        if upstream_interface.count(".") == 1  # Skip sub-interfaces
    }


def compare_locales(upstream_locales: dict[str, set[str]]) -> tuple[list[str], list[str], list[str]]:
    interfaces_missing = []
    interfaces_nok = []
    interfaces_ok = []

    for upstream_interface, upstream_locale in upstream_locales.items():
        core_interface_name = upstream_interface.replace(".", "")
        core_interface = getattr(capabilities, core_interface_name, None)

        if core_interface is None:
            interfaces_missing.append(upstream_interface)
            continue

        core_locale = core_interface.supported_locales

        if not upstream_locale.issubset(core_locale):
            interfaces_nok.append(core_interface_name)
        else:
            interfaces_ok.append(core_interface_name)

    return interfaces_missing, interfaces_nok, interfaces_ok


def run_script() -> None:
    try:
        html_content = fetch_data(SITE, TIMEOUT)
        data = parse_html(html_content)
        upstream_locales = extract_locales(data)
        interfaces_missing, interfaces_nok, interfaces_ok = compare_locales(upstream_locales)

        logging.info("Missing interfaces: %s", interfaces_missing)
        logging.info("Interfaces where upstream locales are not subsets of the core locales: %s", interfaces_nok)
        logging.info("Interfaces checked ok: %s", interfaces_ok)

    except Exception as e:
        logging.exception("An error occurred during script execution: %s", e)


if __name__ == "__main__":
    run_script()
