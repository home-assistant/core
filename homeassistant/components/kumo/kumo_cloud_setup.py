#!/usr/bin/env python3
"""Fetch required info from KumoCloud and produce HomeAssistant configuration section for the units found there."""

import getpass

import requests


def main():
    """Entry point."""
    username = input("KumoCloud username:")
    password = getpass.getpass(prompt="KumoCloud password:")

    url = "https://geo-c.kumocloud.com/login"
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "en-US,en",
        "Content-Type": "application/json",
    }
    body = f'{{"username":"{username}","password":"{password}","appVersion":"2.2.0"}}'
    print("body: %s" % str(body))
    response = requests.post(url, headers=headers, data=body)
    kumo_dict = response.json()
    print("response: %s" % str(kumo_dict))

    print(
        "# Configuration for Kumo units '%s' for %s"
        % (kumo_dict[2]["label"], kumo_dict[0]["username"])
    )
    print("climate:")
    for child in kumo_dict[2]["children"]:
        for zone in child["zoneTable"].values():
            print("  - platform: kumo")
            print('    name: "%s"' % zone["label"])
            print('    address: "%s"' % zone["address"])
            print(
                '    config: \'{"password": "%s", "crypto_serial":"%s"}\''
                % (zone["password"], zone["cryptoSerial"])
            )


if __name__ == "__main__":
    main()
