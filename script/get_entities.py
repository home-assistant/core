#! /usr/bin/python
"""
Query the Home Assistant API for available entities then print them and any
desired attributes to the screen.
"""

import sys
import getpass
import argparse
try:
    from urllib2 import urlopen
    PYTHON = 2
except ImportError:
    from urllib.request import urlopen
    PYTHON = 3
import json


def main(password, askpass, attrs, address, port):
    """ fetch Home Assistant api json page and post process """
    # ask for password
    if askpass:
        password = getpass.getpass('Home Assistant API Password: ')

    # fetch API result
    url = mk_url(address, port, password)
    response = urlopen(url).read()
    if PYTHON == 3:
        response = response.decode('utf-8')
    data = json.loads(response)

    # parse data
    output = {'entity_id': []}
    output.update([(attr, []) for attr in attrs])
    for item in data:
        output['entity_id'].append(item['entity_id'])
        for attr in attrs:
            output[attr].append(item['attributes'].get(attr, ''))

    # output data
    print_table(output, ['entity_id'] + attrs)


def print_table(data, columns):
    """ format and print a table of data from a dictionary """
    # get column lengths
    lengths = {}
    for key, value in data.items():
        lengths[key] = max([len(str(val)) for val in value] + [len(key)])

    # print header
    for item in columns:
        itemup = item.upper()
        sys.stdout.write(itemup + ' ' * (lengths[item] - len(item) + 4))
    sys.stdout.write('\n')

    # print body
    for ind in range(len(data[columns[0]])):
        for item in columns:
            val = str(data[item][ind])
            sys.stdout.write(val + ' ' * (lengths[item] - len(val) + 4))
        sys.stdout.write("\n")


def mk_url(address, port, password):
    """ construct the url call for the api states page """
    url = ''
    if address.startswith('http://'):
        url += address
    else:
        url += 'http://' + address
    url += ':' + port + '/api/states?'
    if password is not None:
        url += 'api_password=' + password
    return url


if __name__ == "__main__":
    all_options = {'password': None, 'askpass': False, 'attrs': [],
                   'address': 'localhost', 'port': '8123'}

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('attrs', metavar='ATTRIBUTE', type=str, nargs='*',
                        help='an attribute to read from the state')
    parser.add_argument('--password', dest='password', default=None,
                        type=str, help='API password for the HA server')
    parser.add_argument('--ask-password', dest='askpass', default=False,
                        action='store_const', const=True,
                        help='prompt for HA API password')
    parser.add_argument('--addr', dest='address',
                        default='localhost', type=str,
                        help='address of the HA server')
    parser.add_argument('--port', dest='port', default='8123',
                        type=str, help='port that HA is hosting on')

    args = parser.parse_args()
    main(args.password, args.askpass, args.attrs, args.address, args.port)
