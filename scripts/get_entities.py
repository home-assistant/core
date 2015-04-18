#! /usr/bin/python
"""
get_entities.py

Usage: get_entities.py [OPTION] ... [ATTRIBUTE] ...

Query the Home Assistant API for available entities then print them and any
desired attributes to the screen.

Options:
    -h, --help                      display this text
        --password=PASS             use the supplied password
        --ask-password              prompt for password
    -a, --address=ADDR              use the supplied server address
    -p, --port=PORT                 use the supplied server port
"""
import sys
import getpass
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


def parse(option, all_options):
    """ either update the options or set it to be updated next time """
    if len(option) > 1:
        all_options[option[0]] = option[1]
        return (all_options, None)
    else:
        return (all_options, option)


if __name__ == "__main__":
    all_options = {'password': None, 'askpass': False, 'attrs': [],
                   'address': 'localhost', 'port': '8123'}

    # parse arguments
    next_key = None
    for arg in sys.argv[1:]:
        if next_key is None:
            option = arg.split('=')

            if option[0] in ['-h', '--help']:
                print(__doc__)
                sys.exit(0)

            elif option[0] == '--password':
                all_options['password'] = '='.join(option[1:])

            elif option[0] == '--ask-password':
                all_options['askpass'] = True

            elif option[0] == '-a':
                next_key = 'address'

            elif option[0] == '--address':
                all_options['address'] = '='.join(option[1:])

            elif option[0] == '-p':
                next_key = 'port'

            elif option[0] == '--port':
                all_options['port'] = '='.join(option[1])

            else:
                all_options['attrs'].append('='.join(option))

        else:
            all_options[next_key] = arg
            next_key = None

    main(**all_options)
