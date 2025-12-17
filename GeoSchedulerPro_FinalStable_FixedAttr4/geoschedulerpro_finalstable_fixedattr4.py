from qgis.PyQt import QtWidgets
from .geoschedulerpro_finalstable_fixedattr4_dialog import GeoSchedulerProFinalStableFixedAttr4Dialog

class GeoSchedulerProFinalStableFixedAttr4:
    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.dialog = None

    def initGui(self):
        self.action = QtWidgets.QAction('GeoScheduler Pro (Stable Fixed Attr4)', self.iface.mainWindow())
        self.action.triggered.connect(self.run)
        self.iface.addPluginToMenu('GeoScheduler Pro (Stable Fixed Attr4)', self.action)
        self.iface.addToolBarIcon(self.action)

    def unload(self):
        if self.action:
            self.iface.removePluginMenu('GeoScheduler Pro (Stable Fixed Attr4)', self.action)
            self.iface.removeToolBarIcon(self.action)

    def run(self):
        if not self.dialog:
            self.dialog = GeoSchedulerProFinalStableFixedAttr4Dialog(self.iface)
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()
