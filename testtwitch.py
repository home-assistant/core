from twitch import TwitchClient

client = TwitchClient(client_id='uq0whcvbh75kuy1g9xvu7i2n1xa9gr')
channel = client.channels.get_by_id(44322889)

print(channel.id)
print(channel.name)
print(channel.display_name)


