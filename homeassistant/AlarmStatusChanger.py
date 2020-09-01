
#
# This scripts generates an html file based on a directory of mp4 videos. 

#Instructions:
#
# Install ffmpeg for your platform
# Install python3 and pip3
# pip install ffmpy yattag python-crontab

import argparse
from yattag import Doc
doc, tag, text = Doc().tagtext()
import sqlite3
from sqlite3 import Error

class DBAccess:
    def __init__(self, db_file):
        self.conn = None
        try:
            self.conn = sqlite3.connect(db_file)
        except Error as e:
            a=1

    def getState(self, ID):
        try:
            cur = self.conn.cursor()
            cur.execute("SELECT AlarmStatus FROM AreaMonitoring WHERE areaid=?", (ID,))
            rows = cur.fetchall()
            state = rows[0][0]
            return state
        except:
            return "error"

    def setState(self, ID, state):
        try:
            cur = self.conn.cursor()
            if ID == 'all':
                sql = 'Update AreaMonitoring set AlarmStatus = ?'
                data = (state, )
            else:
                sql = 'Update AreaMonitoring set AlarmStatus = ? where areaid = ?'
                data = (state, ID)
            cur.execute(sql, data)
            self.conn.commit()
        except:
            return False
        return True

class AlarmStatusChanger:

    def __init__(self):
        self.theDB = DBAccess('/home/dionisis/PycharmProjects/Guard/SQLLiteDB/TrackedObjects.db')

    def clear(self,ID):
        self.theDB.setState(ID,1)

    def escalate(self,ID):
        self.theDB.setState(ID,4)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='This script resets or escalates the alarm status of a home')
    parser.add_argument('-i', '--id', help='master area id of the home.', default='all')
    parser.add_argument('-a', '--action',
                        help='clear or escalate',
                        required=True)
    args = parser.parse_args()

    id = args.id
    newStatus = args.action


    theStatusChanger = AlarmStatusChanger()

    if newStatus == 'clear':
        theStatusChanger.clear(id)
    elif newStatus == 'escalate':
        theStatusChanger.escalate(id)
