import pytest
from history_generator import history_generator

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

def test_history_generator_1():
    assert history_generator(history_example_1, './files/history1.txt') == True # Arquivo foi criado e existe no path passado como parâmetro

def test_history_generator_2():
    assert history_generator(list_dict, './files/history3.txt') == True # Arquivo foi criado e existe no path passado como parâmetro