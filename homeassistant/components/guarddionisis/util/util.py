"""Define Guard specific utilities."""
from concurrent import futures
import importlib
import sqlite3
from sqlite3 import Error
from typing import Any, Mapping
import logging


#sensor_pb2 = importlib.util.spec_from_file_location("sensor_pb2", "/Users/dionisis/Code/GitHub/core/homeassistant/components/guarddionisis/util/sensor_pb2.py")
#sensor_pb2_grpc = importlib.util.spec_from_file_location("sensor_pb2_grpc", "/Users/dionisis/Code/GitHub/core/homeassistant/components/guarddionisis/util/sensor_pb2_grpc.py")

import grpc
import homeassistant.components.guarddionisis.util.sensor_pb2 as sensor_pb2
import homeassistant.components.guarddionisis.util.sensor_pb2_grpc as sensor_pb2_grpc

from homeassistant.core import HomeAssistant, State


_LOGGER = logging.getLogger(__name__)


class Util:
    def serve(self,hass):
        server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        sensor_pb2_grpc.add_SensorServiceServicer_to_server(SensorServicer(hass), server)
        server.add_insecure_port('[::]:52751')
        server.start()
        print("gRPC server started. Listening on port 52751.")
        server.wait_for_termination()

class DBAccess:
    def __init__(self, db_file):
        self.conn = None
        try:
            self.conn = sqlite3.connect(db_file)
        except Error as e:
            a=1

    def getAreaCounter(self, ID):
        try:
            cur = self.conn.cursor()
            cur.execute("SELECT counted FROM AreaMonitoring WHERE AreaID=?", (ID,))
            rows = cur.fetchall()
            state = rows[0][0]
            cur.close()
            return state
        except:
            return -1
        
    def setAreaCounter(self, ID, status):
        try:
            cur = self.conn.cursor()
            sql = 'Update AreaMonitoring set counted = ? where AreaID = ?'
            data = (status, ID)
            cur.execute(sql, data)
            self.conn.commit()
            cur.close()
        except:
            return False
        return True

    def getRegionCounter(self, ID):
        try:
            cur = self.conn.cursor()
            cur.execute("SELECT count FROM RegionMonitoring WHERE RegionID=?", (ID,))
            rows = cur.fetchall()
            state = rows[0][0]
            cur.close()
            return state
        except:
            return -1
        
    def setRegionCounter(self, ID, status):
        try:
            cur = self.conn.cursor()
            sql = 'Update RegionMonitoring set count = ? where RegionID = ?'
            data = (status, ID)
            cur.execute(sql, data)
            self.conn.commit()
            cur.close()
        except:
            return False
        return True



    def getAlarmSensorStatus(self, ID):
        try:
            cur = self.conn.cursor()
            cur.execute("SELECT AlarmStatus FROM AreaMonitoring WHERE AreaID=?", (ID,))
            rows = cur.fetchall()
            state = rows[0][0]
            cur.close()
            return state
        except:
            return -1
        
    def setAlarmSensorStatus(self, ID, status):
        try:
            cur = self.conn.cursor()
            sql = 'Update AreaMonitoring set AlarmStatus = ? where AreaID = ?'
            data = (status, ID)
            cur.execute(sql, data)
            self.conn.commit()
            cur.close()
        except:
            return False
        return True
    
    def getAlarmState(self, ID):
        try:
            cur = self.conn.cursor()
            cur.execute("SELECT HAAlarmState FROM Areas WHERE ID=?", (ID,))
            rows = cur.fetchall()
            cur.close()
            state = rows[0][0]
            return state
        except Error as e:
            _LOGGER.error("AlarmDionisis DB exception:" + str(e))
            return "error"

    async def setAlarmState(self, ID, state):
        try:
            cur = self.conn.cursor()
            sql = 'Update Areas set HAAlarmState = ? where id = ?'
            data = (state, ID)
            cur.execute(sql, data)
            self.conn.commit()
            cur.close()
        except Error as e:
            _LOGGER.error("AlarmDionisis DB exception:" + str(e))
            return False
        return True

    async def Disarm(self, ID):
        try:
            cur = self.conn.cursor()
            #sql = 'Update ROIs set active = 1 where id in (select roi_id from roisinareas inner join areas on roisinareas.area_id = areas.id where areas.MasterArea_ID = ?) and type in ("gate","entrance","passage")'
            sql = 'Update ROIs set active = 1 where type in ("gate","entrance","passage")'
            data = (ID,)
            cur.execute(sql)
            self.conn.commit()
            cur.close()
        except Error as e:
            _LOGGER.error("AlarmDionisis DB exception:" + str(e))
            return False
        return True

    async def ArmDay(self, ID):
        try:
            cur = self.conn.cursor()
            sql = 'Update ROIs set active = 1 where id in (select roi_id from roisinareas inner join areas on roisinareas.area_id = areas.id where areas.MasterArea_ID = ?) and type in ("gate","entrance","passage")'
            data = (ID,)
            cur.execute(sql)
            self.conn.commit()
            cur.close()
        except Error as e:
            _LOGGER.error("AlarmDionisis DB exception:" + str(e))
            return False
        return True

    async def ArmNight(self, ID):
        try:
            cur = self.conn.cursor()
            #sql = 'Update ROIs set active = 0 where id in (select roi_id from roisinareas inner join areas on roisinareas.area_id = areas.id where areas.MasterArea_ID = ?) and type in ("gate","entrance")'
            sql = 'Update ROIs set active = 0 where type in ("gate","entrance")'
            data = (ID,)
            cur.execute(sql)

            #sql = 'Update ROIs set active = 1 where id in (select roi_id from roisinareas inner join areas on roisinareas.area_id = areas.id where areas.MasterArea_ID = ?) and type in ("passage")'
            sql = 'Update ROIs set active = 1 where type in ("passage")'
            data = (ID,)
            cur.execute(sql)
            
            #sql = 'Update AreaMonitoring set counted = 0 where areaid in (select id from areas where masterarea_ID = ? and AreaType = \'perimeter\')'
            sql = 'Update AreaMonitoring set counted = 0 where areaid in (select id from areas where AreaType = \'perimeter\')'
            data = (ID,)
            cur.execute(sql)

            self.conn.commit()
            cur.close()
        except Error as e:
            _LOGGER.error("AlarmDionisis DB exception:" + str(e))
            return False
        return True

    async def ArmHome(self, ID):
        try:
            cur = self.conn.cursor()
            #dionisis thelei douleia edw
            #sql = 'Update ROIs set active = 0 where id in (select roi_id from roisinareas inner join areas on roisinareas.area_id = areas.id where areas.MasterArea_ID = ?) and type in ("entrance")'
            sql = 'Update ROIs set active = 0 where type in ("entrance")'
            data = (ID,)
            cur.execute(sql)

            #sql = 'Update ROIs set active = 1 where id in (select roi_id from roisinareas inner join areas on roisinareas.area_id = areas.id where areas.MasterArea_ID = ?) and type in ("gate","passage")'
            sql = 'Update ROIs set active = 1 where type in ("gate","passage")'
            data = (ID,)
            cur.execute(sql)
            self.conn.commit()
        except Error as e:
            _LOGGER.error("AlarmDionisis DB exception:" + str(e))
            return False
        return True

    async def ArmAway(self, ID):
        try:
            cur = self.conn.cursor()
            #sql = 'Update ROIs set active = 0 where id in (select roi_id from roisinareas inner join areas on roisinareas.area_id = areas.id where areas.MasterArea_ID = ?) and type in ("gate","entrance","passage")'
            sql = 'Update ROIs set active = 0 where type in ("gate","entrance","passage")'
            data = (ID,)
            cur.execute(sql)

            #sql = 'Update AreaMonitoring set counted = 0 where areaid in (select id from areas where masterarea_ID = ?)'
            #data = (ID,)
            #cur.execute(sql, data)

            self.conn.commit()
            cur.close()
        except Error as e:
            _LOGGER.error("AlarmDionisis DB exception:"+str(e))
            return False
        return True



class SensorServicer(sensor_pb2_grpc.SensorServiceServicer):
    def __init__(self,hass:HomeAssistant):
        self.sensor_data = None
        self.hass = hass

    def GetSensorData(self, request, context):
        return 0

    def SetSensorData(self, request, context):
        self.test = request.value
        #llll = self.hass.states
        #self.hass.states._states["sensor.internal"]= request.value
        print("SetSensorData entity:"+str(request.entity_id)+" value:"+str(request.value))

        entity = self.hass.states.get(request.entity_id)
        attr = entity.attributes#{'unit_of_measurement':'People'}


        #self.hass.services.call('sensor', 'set_state', {'entity_id': request.entity_id, 'value':  request.value})

        #new_state = State(request.entity_id, request.value, dict(entity.attributes))

        self.hass.states.set(request.entity_id, request.value,attr)

        return sensor_pb2.Void()
    



