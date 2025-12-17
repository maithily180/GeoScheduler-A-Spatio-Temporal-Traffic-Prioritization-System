from qgis.PyQt import QtWidgets
from .geoschedulerpro_finalstable_traffickers_fixedv3_dialog import GeoSchedulerProFinalStableTraffickersFixedV3Dialog

class GeoSchedulerProFinalStableTraffickersFixedV3:
    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.dialog = None

    def initGui(self):
        self.action = QtWidgets.QAction('GeoScheduler Pro (Traffickers Fixed V3)', self.iface.mainWindow())
        self.action.triggered.connect(self.run)
        self.iface.addPluginToMenu('GeoScheduler Pro (Traffickers Fixed V3)', self.action)
        self.iface.addToolBarIcon(self.action)

    def unload(self):
        if self.action:
            self.iface.removePluginMenu('GeoScheduler Pro (Traffickers Fixed V3)', self.action)
            self.iface.removeToolBarIcon(self.action)

    def run(self):
        if not self.dialog:
            self.dialog = GeoSchedulerProFinalStableTraffickersFixedV3Dialog(self.iface)
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()
