#!/usr/bin/env python3

"""Download the latest Polymer v1 iconset for materialdesignicons.com."""
import gzip
import os
import re
import requests
import sys

from fingerprint_frontend import fingerprint

GETTING_STARTED_URL = ('https://raw.githubusercontent.com/Templarian/'
                       'MaterialDesign/master/site/getting-started.savvy')
DOWNLOAD_LINK = re.compile(r'(/api/download/polymer/v1/([A-Z0-9-]{36}))')
START_ICONSET = '<iron-iconset-svg'

OUTPUT_BASE = os.path.join('homeassistant', 'components', 'frontend')
ICONSET_OUTPUT = os.path.join(OUTPUT_BASE, 'www_static', 'mdi.html')
ICONSET_OUTPUT_GZ = os.path.join(OUTPUT_BASE, 'www_static', 'mdi.html.gz')


def get_remote_version():
    """Get current version and download link."""
    gs_page = requests.get(GETTING_STARTED_URL).text

    mdi_download = re.search(DOWNLOAD_LINK, gs_page)

    if not mdi_download:
        print("Unable to find download link")
        sys.exit()

    return 'https://materialdesignicons.com' + mdi_download.group(1)


def clean_component(source):
    """Clean component."""
    return source[source.index(START_ICONSET):]


def write_component(source):
    """Write component."""
    with open(ICONSET_OUTPUT, 'w') as outp:
        print('Writing icons to', ICONSET_OUTPUT)
        outp.write(source)

    with gzip.open(ICONSET_OUTPUT_GZ, 'wb') as outp:
        print('Writing icons gz to', ICONSET_OUTPUT_GZ)
        outp.write(source.encode('utf-8'))


def main():
    """Main section of the script."""
    # All scripts should have their current work dir set to project root
    if os.path.basename(os.getcwd()) == 'script':
        os.chdir('..')

    print("materialdesignicons.com icon updater")

    remote_url = get_remote_version()
    source = clean_component(requests.get(remote_url).text)
    write_component(source)
    fingerprint()

    print('Updated to latest version')

if __name__ == '__main__':
    main()
