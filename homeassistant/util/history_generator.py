import os.path

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