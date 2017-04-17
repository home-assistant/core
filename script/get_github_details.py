#! /usr/bin/python3
"""
Simple script to get the first and the last commit of a component/platform.

This could help with the identification of the person who developed the
component/platform and can run test locally while fixing bugs.
"""
import sys
import argparse
import requests

URL = 'https://api.github.com/repos/balloob/home-assistant'
EXCLUDE = ['services.yaml',
           'addtrustexternalcaroot.crt',
           'index.html.template',
           'www_static',
           'light_profiles.csv']

def get_all(token):
    """ Retrieve details for all components/platforms from GitHub. """
    resp = requests.get('{}/{}'.format(URL,
                                       'contents/homeassistant/components'),
                        headers={'Authorization': 'token {}'.format(token)},
                        timeout=10)
    for entry in resp.json():
        if entry['type'] == 'dir':
            sub_resp = requests.get('{}/{}/{}'.format(URL, 'contents',
                                                      entry['path']),
                                    headers={'Authorization':
                                                 'token {}'.format(token)},
                                    timeout=10)
            for file in sub_resp.json():
                if file['path'].split('/')[-1] not in EXCLUDE:
                    component = '.'.join([file['path'].split('/')[-2],
                                          file['path'].split('/')[-1]])
                    get_single(token, component[:-3])
        else:
            component = entry['path'].split('/')[-1]
            get_single(token, component[:-3])

def get_single(token, component):
    """ Fetch the details for a component/platform from GitHub. """
    try:
        path = '/'.join(component.split('.'))
    except AttributeError:
        path = component
    payload = {'path': 'homeassistant/components/{}.py'.format(path)}

    resp = requests.get('{}/{}'.format(URL, 'commits'),
                        headers={'Authorization': 'token {}'.format(token)},
                        params=payload, timeout=10)

    if not resp.json():
        print('Please check your component/platform entry.')
        sys.exit(1)

    try:
        # First commit
        try:
            first_commit = resp.json()[-1]
            print(component, '\n',
                  '  First commit: ',
                  first_commit['committer']['login'], '\t',
                  first_commit['commit']['author']['date'])
        except KeyError:
            print('Please check your GitHub API token.')
            sys.exit(1)
        # Last commit
        last_commit = resp.json()[0]
        print('   Last commit:  ',
              last_commit['committer']['login'], '\t',
              last_commit['commit']['author']['date'])
    except TypeError:
        pass
    # For a link to the commit add "last_commit['html_url']"

def argparsing():
    """ Parsing the command line arguments. """
    parser = argparse.ArgumentParser(description='Retrieve details about a '
                                                 'component/platform from '
                                                 'GitHub.')
    parser.add_argument('component', type=str, nargs='?',
                        help='a component/platform to get details about')
    parser.add_argument('-t', '--token', type=str, help='GitHub API token')

    return parser.parse_args()

def main():
    """ Fetch the details for a component/platform from GitHub. """
    args = argparsing()
    if args.component:
        get_single(args.token, args.component)
    else:
        get_all(args.token)

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print('Interrupted, exiting...')
        sys.exit(1)
