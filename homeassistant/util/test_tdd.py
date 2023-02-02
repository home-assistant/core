import pytest
import os.path

history_example_1 = {
    "id": 1,
    "device": 'Alexa',
    "date": '01-23-2023',
    "additionals": 'Alexa was called 5 times this day, interacting for 60 minutes.' 
}

history_example_2 = {
    "id": 2,
    "device": 'Thermometer',
    "date": '02-01-2023',
    "additionals": 'The average temperature this day was 25°C.' 
}

list_dict = [history_example_1, history_example_2]

def history_generator(list_dict, file_path):
    table = "| id | device |    date    | additionals |"
    for d in list_dict:
        id_history = d["id"]
        device = d["device"]
        date = d["date"]
        additionals = d["additionals"]
        table += f"\n| {id_history} | {device} | {date} | {additionals} |"
    f = open(file_path, 'w')
    f.write(table)
    f.close()
    f = open(file_path, 'r')
    same = (table == f.read())
    f.close()
    return same

def test_history_generator():
    assert history_generator(list_dict, './files/history3.txt') == True # Arquivo foi criado e existe no path passado como parâmetro