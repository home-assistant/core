=====
Usage
=====

To use locationsharinglib in a project:

.. code-block:: python

    from locationsharinglib import Service
    service = Service(username, password, cookies_file="YOUR_COOKIES_FILE")
    for person in service.get_all_people():
        print(person)


To get the cookies you can use the cli tool:

.. code-block:: bash

    $ get-maps-cookies --help
    usage: get-maps-cookies [-h] --email EMAIL --password PASSWORD
                            [--cookies-file COOKIES_FILE]

    A tool to interactively handle authentication for google maps and 2FA

    optional arguments:
      -h, --help            show this help message and exit
      --email EMAIL, -e EMAIL
                            The email of the account to authenticate
      --password PASSWORD, -p PASSWORD
                            The password of the account to authenticate
      --cookies-file COOKIES_FILE, -c COOKIES_FILE
                            The file to output the cookies to
