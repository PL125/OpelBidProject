# This Python file uses the following encoding: utf-8
import os
from pathlib import Path
import sys
import can
import cardata
import threading
from easysettings import EasySettings
from datetime import datetime

from PyQt5.QtGui import QGuiApplication
from PySide2.QtQml import QQmlApplicationEngine
from PySide2 import QtCore
from PySide2.QtCore import QObject, Signal, Slot


class MainWindow(QObject):
    def __init__(self):
        QObject.__init__(self)

    settings = EasySettings("settings.conf")

    isCanOnline = Signal(bool)
    speed = Signal(float)
    rpm = Signal(int)
    engineTemp = Signal(int)
    airTemp = Signal(float)
    fuelPercentage = Signal(float)
    estRange = Signal(float)
    averageConsumption = Signal(str)
    instantConsumption = Signal(float)
    isEngineRunning = Signal(bool)
    isCruiseControlActive = Signal(bool)
    triggeredControl = Signal(dict)

    @Slot(str, str)
    def setSetting(self, setting, value):
        self.settings.set(setting, value)
        self.settings.save()

    @Slot(str, result=str)
    def getSetting(self, setting):
        if self.settings.has_option(setting):
            return self.settings.get(setting)
        else:
            return None

    def emitDefaults(self):
        self.isEngineRunning.emit(False)
        self.isCanOnline.emit(False)

    bus = None

    # define can information for MCP2515 and GMLAN Single Wire Can (LSCAN)
    try:
        bus = can.interface.Bus(bustype='socketcan',
                                channel='can0', bitrate=33300)
    except:
        print("Can bus başlatılamıyor.")

    def canLoop(self):
        if self.bus is not None:
            self.isCanOnline.emit(True)
            while True:
                msg = self.bus.recv()
                self.checkCanMessage(msg.arbitration_id,  msg.data)
        else:
            while True:
                #print("Can bağlantısı sağlanamadı. Yeniden deneniyor...")
                try:
                    self.bus = can.interface.Bus(bustype='socketcan',
                                                 channel='can0', bitrate=33300)
                except:
                    continue
                if self.bus is not None:
                    self.canLoop()
                    break
            self.isCanOnline.emit(False)

    thread = None

    def startCanLoop(self):
        self.thread = threading.Thread(target=self.canLoop, daemon=True)
        self.thread.start()

    def checkCanMessage(self, id, data):
        if(cardata.canMessages[id] == 'MOTION'):
            self.updateMotionData(data)
        elif(cardata.canMessages[id] == 'ENGINE'):
            self.updateEngineData(data)
        elif(cardata.canMessages[id] == 'AIR_TEMP'):
            self.updateAirTemp(data)
        elif(cardata.canMessages[id] == 'FUEL_LEVEL'):
            self.updateFuelLevel(data)
        elif(cardata.canMessages[id] == 'SW_CONTROL'):
            self.triggerSWControl(data)

    def updateMotionData(self, data):
        motionData = cardata.humanizeMotionData(data)
        self.speed.emit(motionData["speed"])
        self.rpm.emit(motionData["rpm"]/100)

    def updateEngineData(self, data):
        engineData = cardata.humanizeEngineData(data)
        self.engineTemp.emit(engineData["engineTemp"])
        self.isEngineRunning.emit(engineData["isEngineRunning"])
        self.isCruiseControlActive.emit(engineData["isCruiseControlActive"])

    def updateAirTemp(self, data):
        airTemp = cardata.humanizeAirTemp(data)
        self.airTemp.emit(airTemp)

    def updateFuelLevel(self, data):
        fuelLevel = cardata.humanizeFuelLevel(data)
        self.fuelPercentage.emit((fuelLevel * 100) / cardata.fuelCapacity)

    def triggerSWControl(self, data):
        triggeredControls = cardata.humanizeSWControls(data)
        for triggeredControl in triggeredControls:
            timestamp = datetime.timestamp(datetime.now())
            triggeredControlObject = {
                "control": triggeredControl, "time": timestamp}
            self.triggeredControl.emit(triggeredControlObject)


if __name__ == "__main__":
    app = QGuiApplication(sys.argv)
    engine = QQmlApplicationEngine()
    main = MainWindow()
    engine.rootContext().setContextProperty("backend", main)
    engine.load(os.fspath(Path(__file__).resolve().parent / "main.qml"))
    main.emitDefaults()
    main.startCanLoop()
    if not engine.rootObjects():
        sys.exit(-1)
    sys.exit(app.exec())
