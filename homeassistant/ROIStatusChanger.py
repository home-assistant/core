
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

    def setRegionCount(self, ID, count):
        try:
            cur = self.conn.cursor()
            sql = 'Update RegionMonitoring set count = ? where RegionID = ?'
            data = (int(count), int(ID))
            cur.execute(sql, data)
            self.conn.commit()
        except:
            return False
        return True

    def setAreaCount(self, ID, count):
        try:
            cur = self.conn.cursor()
            sql = 'Update AreaMonitoring set count = ? where AreaID = ?'
            data = (count, ID)
            cur.execute(sql, data)
            self.conn.commit()
        except:
            return False
        return True

    def setStatus(self, ID, status):
        try:
            cur = self.conn.cursor()
            if ID == 'all':
                sql = 'Update ROIs set Active = ?'
                data = (status, )
            else:
                sql = 'Update ROIs set Active = ? where ID = ?'
                data = (status, int(ID))
            cur.execute(sql, data)
            self.conn.commit()
        except:
            return False
        return True


class ROIStatusChanger:

    def __init__(self):
        self.theDB = DBAccess('/home/dionisis/PycharmProjects/Guard/SQLLiteDB/TrackedObjects.db')

    def setROIStatus(self,ID,status):
        self.theDB.setStatus(ID,status)

    def setRegionCount(self,ID,count):
        self.theDB.setRegionCount(ID,count)

    def setAreaCount(self,ID,count):
        self.theDB.setAreaCount(ID,count)



if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description='This script resets or escalates the alarm status of a home')
    parser.add_argument('-i', '--id', help='ROI id', default='all')
    parser.add_argument('-a', '--action',
                        help='enable or disable',
                        required=True)
    parser.add_argument('-t', '--type',
                        help='ROI Type: Area or Region',
                        required=True)
    parser.add_argument('-c', '--count',
                        help='new ROI count',
                        required=False)
    args = parser.parse_args()


    theStatusChanger = ROIStatusChanger()

    id = args.id
    newStatus = args.action
    ROIType = args.type

    if args.count:
        count = args.count
        if ROIType == "Area":
            theStatusChanger.setAreaCount(id,count)
        elif ROIType == "Region":
            theStatusChanger.setRegionCount(id,count)


    if newStatus == 'enable':
        theStatusChanger.setROIStatus(id,1)
    elif newStatus == 'disable':
        theStatusChanger.setROIStatus(id,0)
