from qbittorrent.client import Client


def get_main_data_client(client: Client):
    return client.sync_main_data()


def create_client(url, username, password):
    client = Client(url)
    client.login(username, password)
    return client

def retrieve_torrentdata(client: Client, torrentfilter):
    return client.torrents(filter=torrentfilter)