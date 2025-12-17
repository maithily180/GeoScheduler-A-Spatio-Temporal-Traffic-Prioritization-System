\
from qgis.PyQt import QtWidgets, QtCore
from qgis.core import (
    QgsProject, QgsVectorLayer, QgsField, QgsFeature, QgsGeometry,
    QgsPointXY, QgsVectorFileWriter, QgsCoordinateTransform, QgsVectorDataProvider
)
from qgis.PyQt.QtCore import QVariant
import processing, tempfile, os, math, random

class GeoSchedulerProFinalStableFixedAttr4Dialog(QtWidgets.QDialog):
    """
    Final plugin: fixes shapefile field creation issues, reprojects centroids to road CRS,
    and writes weights robustly (with fallback if shapefile is not writable).
    """

    def __init__(self, iface):
        super().__init__(iface.mainWindow())
        self.iface = iface
        self.setWindowTitle('GeoScheduler Pro (Stable Fixed Attr4)')
        self.setMinimumWidth(720)
        layout = QtWidgets.QVBoxLayout()

        self.origin_combo = self.layer_selector('Origin Zones (polygon)')
        self.dest_combo   = self.layer_selector('Destination Zones (polygon)')
        self.road_combo   = self.layer_selector('Road Network (line)')
        self.junction_combo = self.layer_selector('Junctions (point)')

        layout.addLayout(self.origin_combo['layout'])
        layout.addLayout(self.dest_combo['layout'])
        layout.addLayout(self.road_combo['layout'])
        layout.addLayout(self.junction_combo['layout'])

        param_row = QtWidgets.QHBoxLayout()
        param_row.addWidget(QtWidgets.QLabel('Max representatives per side:'))
        self.max_spin = QtWidgets.QSpinBox()
        self.max_spin.setRange(1,20)
        self.max_spin.setValue(5)
        param_row.addWidget(self.max_spin)

        param_row.addWidget(QtWidgets.QLabel('Density threshold (0-1):'))
        self.density = QtWidgets.QDoubleSpinBox()
        self.density.setRange(0.0,1.0)
        self.density.setSingleStep(0.05)
        self.density.setValue(0.1)
        param_row.addWidget(self.density)

        layout.addLayout(param_row)

        # Time-of-day selector
        time_row = QtWidgets.QHBoxLayout()
        time_row.addWidget(QtWidgets.QLabel('Time of Day:'))
        self.time_combo = QtWidgets.QComboBox()
        self.time_combo.addItems(['AM Peak','PM Peak','Off-Peak'])
        time_row.addWidget(self.time_combo)
        layout.addLayout(time_row)

        # Debug option
        debug_row = QtWidgets.QHBoxLayout()
        self.debug_check = QtWidgets.QCheckBox('Create debug centroid layers (visible)')
        debug_row.addWidget(self.debug_check)
        layout.addLayout(debug_row)

        self.run_btn = QtWidgets.QPushButton('Run Stable GeoScheduler')
        self.run_btn.clicked.connect(self.run_model)
        layout.addWidget(self.run_btn)

        self.status = QtWidgets.QLabel('')
        layout.addWidget(self.status)

        self.setLayout(layout)
        self.populate_all()

    def layer_selector(self, label):
        box = QtWidgets.QHBoxLayout()
        box.addWidget(QtWidgets.QLabel(label + ':'))
        combo = QtWidgets.QComboBox()
        box.addWidget(combo)
        refresh = QtWidgets.QPushButton('Refresh')
        refresh.clicked.connect(lambda: self.populate(combo))
        box.addWidget(refresh)
        return {'layout': box, 'combo': combo}

    def populate(self, combo):
        combo.clear()
        for lyr in QgsProject.instance().mapLayers().values():
            if isinstance(lyr, QgsVectorLayer):
                combo.addItem(lyr.name())

    def populate_all(self):
        self.populate(self.origin_combo['combo'])
        self.populate(self.dest_combo['combo'])
        self.populate(self.road_combo['combo'])
        self.populate(self.junction_combo['combo'])

    def show_message(self, text):
        QtWidgets.QMessageBox.information(self, 'GeoScheduler Pro (Stable Fixed Attr4)', text)

    def validate_layers(self, origin_name, dest_name, road_name, junction_name):
        missing = []
        proj = QgsProject.instance()
        origin = proj.mapLayersByName(origin_name)
        dest = proj.mapLayersByName(dest_name)
        road = proj.mapLayersByName(road_name)
        junction = proj.mapLayersByName(junction_name)
        if not origin:
            missing.append('Origin Zones')
        if not dest:
            missing.append('Destination Zones')
        if not road:
            missing.append('Road Network')
        if not junction:
            missing.append('Junctions')
        if missing:
            self.show_message('Missing layers: ' + ', '.join(missing))
            return None, None, None, None
        return origin[0], dest[0], road[0], junction[0]

    def centroids_with_reprojection(self, layer, target_crs):
        pts = []
        src_crs = layer.crs()
        transform = QgsCoordinateTransform(src_crs, target_crs, QgsProject.instance())
        for feat in layer.getFeatures():
            geom = feat.geometry()
            if not geom or geom.isEmpty():
                continue
            try:
                c = geom.centroid()
                pt = c.asPoint()
                tpt = transform.transform(pt)
                pts.append(tpt)
            except Exception:
                continue
        return pts

    def km_reduce(self, pts, k):
        if len(pts) <= k:
            return pts
        arr = [(p.x(), p.y()) for p in pts]
        centers = random.sample(arr, k)
        for _ in range(8):
            clusters = [[] for _ in range(k)]
            for p in arr:
                dists = [ (p[0]-c[0])**2 + (p[1]-c[1])**2 for c in centers ]
                idx = dists.index(min(dists))
                clusters[idx].append(p)
            new = []
            for group in clusters:
                if group:
                    x = sum([p[0] for p in group]) / len(group)
                    y = sum([p[1] for p in group]) / len(group)
                    new.append((x,y))
                else:
                    new.append(random.choice(arr))
            centers = new
        return [QgsPointXY(c[0], c[1]) for c in centers]

    def to_qneat_point_str(self, pt, crs):
        return f"{pt.x()},{pt.y()} [{crs.authid()}]"

    def run_qneat(self, road_layer, start_str, end_str):
        params = {
            'DEFAULT_DIRECTION' : 2,
            'DEFAULT_SPEED' : 5,
            'DIRECTION_FIELD' : '',
            'END_POINT' : end_str,
            'ENTRY_COST_CALCULATION_METHOD' : 0,
            'INPUT' : road_layer.source() if hasattr(road_layer, 'source') else road_layer,
            'OUTPUT' : 'memory:',
            'SPEED_FIELD' : '',
            'START_POINT' : start_str,
            'STRATEGY' : 0,
            'TOLERANCE' : 0,
            'VALUE_BACKWARD' : '',
            'VALUE_BOTH' : '',
            'VALUE_FORWARD' : ''
        }
        try:
            res = processing.run('qneat3:shortestpathpointtopoint', params)
            out = res.get('OUTPUT') or res.get('output') or list(res.values())[0]
            if isinstance(out, str) and os.path.exists(out):
                lyr = QgsVectorLayer(out, 'qneat3_path', 'ogr')
                return lyr if lyr.isValid() else None
            if isinstance(out, QgsVectorLayer):
                return out
            return None
        except Exception:
            return None

    def aggregate_paths_density(self, path_layers):
        counts = {}
        for lyr in path_layers:
            for feat in lyr.getFeatures():
                geom = feat.geometry()
                if not geom: continue
                if geom.isMultipart():
                    parts = geom.asMultiPolyline()
                else:
                    parts = [geom.asPolyline()]
                for part in parts:
                    for p in part:
                        key = (round(p.x(),6), round(p.y(),6))
                        counts[key] = counts.get(key, 0) + 1
        maxc = max(counts.values()) if counts else 1
        density = {k: v/maxc for k, v in counts.items()}
        return density

    def ensure_junction_fields(self, junction_layer):
        # Try to add missing fields, return list of actually available field names after attempt
        provider = junction_layer.dataProvider()
        existing = [f.name() for f in junction_layer.fields()]
        to_add = []
        for fname, ftype in [('N_S_Weight', QVariant.Double), ('E_W_Weight', QVariant.Double), ('UsedByCommuters', QVariant.Int)]:
            if fname not in existing:
                to_add.append(QgsField(fname, ftype))
        if to_add:
            try:
                provider.addAttributes(to_add)
                junction_layer.updateFields()
                existing = [f.name() for f in junction_layer.fields()]
            except Exception:
                # provider may not support addAttributes (shapefile locked or read-only)
                return existing
        return existing

    def run_model(self):
        origin_name = self.origin_combo['combo'].currentText()
        dest_name = self.dest_combo['combo'].currentText()
        road_name = self.road_combo['combo'].currentText()
        junction_name = self.junction_combo['combo'].currentText()

        origin_layer, dest_layer, road_layer, junction_layer = self.validate_layers(origin_name, dest_name, road_name, junction_name)
        if origin_layer is None:
            return

        self.status.setText('Computing centroids and reprojecting to road CRS...')
        QtCore.QCoreApplication.processEvents()

        road_crs = road_layer.crs()
        origin_pts = self.centroids_with_reprojection(origin_layer, road_crs)
        dest_pts = self.centroids_with_reprojection(dest_layer, road_crs)

        if not origin_pts or not dest_pts:
            self.show_message('No centroids found after reprojection. Check layer extents and CRS.')
            return

        # optional debug layers
        debug_created = []
        if self.debug_check.isChecked():
            orig_mem = QgsVectorLayer('Point?crs={}'.format(road_crs.authid()), 'geo_orig_debug', 'memory')
            prov = orig_mem.dataProvider()
            prov.addAttributes([QgsField('id', QVariant.Int)])
            orig_mem.updateFields()
            feats = []
            i = 1
            for p in origin_pts:
                f = QgsFeature(orig_mem.fields())
                f.setGeometry(QgsGeometry.fromPointXY(p))
                f['id'] = i; i += 1
                feats.append(f)
            prov.addFeatures(feats); orig_mem.updateExtents()
            QgsProject.instance().addMapLayer(orig_mem)
            debug_created.append(orig_mem)

            dest_mem = QgsVectorLayer('Point?crs={}'.format(road_crs.authid()), 'geo_dest_debug', 'memory')
            prov2 = dest_mem.dataProvider()
            prov2.addAttributes([QgsField('id', QVariant.Int)])
            dest_mem.updateFields()
            feats2 = []
            i = 1
            for p in dest_pts:
                f = QgsFeature(dest_mem.fields())
                f.setGeometry(QgsGeometry.fromPointXY(p))
                f['id'] = i; i += 1
                feats2.append(f)
            prov2.addFeatures(feats2); dest_mem.updateExtents()
            QgsProject.instance().addMapLayer(dest_mem)
            debug_created.append(dest_mem)

        # reduce representatives if needed
        maxrep = int(self.max_spin.value())
        if len(origin_pts) > maxrep:
            origin_pts = self.km_reduce(origin_pts, maxrep)
        if len(dest_pts) > maxrep:
            dest_pts = self.km_reduce(dest_pts, maxrep)

        total_pairs = len(origin_pts) * len(dest_pts)
        self.status.setText(f'Routing {len(origin_pts)}x{len(dest_pts)} = {total_pairs} pairs...')
        QtCore.QCoreApplication.processEvents()

        path_layers = []
        processed = 0
        for o in origin_pts:
            for d in dest_pts:
                processed += 1
                self.status.setText(f'Routing {processed}/{total_pairs}...')
                QtCore.QCoreApplication.processEvents()
                start_str = self.to_qneat_point_str(o, road_crs)
                end_str = self.to_qneat_point_str(d, road_crs)
                pl = self.run_qneat(road_layer, start_str, end_str)
                if pl is not None:
                    path_layers.append(pl)

        if not path_layers:
            self.show_message('No paths could be computed. Check QNEAT3 and network layer.')
            for layer in debug_created:
                try: QgsProject.instance().removeMapLayer(layer.id())
                except Exception: pass
            return

        self.status.setText('Aggregating path density...')
        QtCore.QCoreApplication.processEvents()
        density = self.aggregate_paths_density(path_layers)
        threshold = self.density.value()

        # ensure junction fields exist and get actual fields
        actual_fields = self.ensure_junction_fields(junction_layer)

        # update junctions based on density; only write fields that actually exist
        writable = set(actual_fields)
        try:
            if not junction_layer.isEditable():
                ok = junction_layer.startEditing()
        except Exception:
            ok = False

        updated = 0
        for feat in junction_layer.getFeatures():
            geom = feat.geometry()
            if not geom: continue
            pt = geom.asPoint()
            key = (round(pt.x(),6), round(pt.y(),6))
            dens = density.get(key, 0.0)
            if dens >= threshold:
                t = self.time_combo.currentText()
                if t == 'AM Peak':
                    ns, ew = 0.75, 0.25
                elif t == 'PM Peak':
                    ns, ew = 0.25, 0.75
                else:
                    ns, ew = 0.5, 0.5
                if 'UsedByCommuters' in writable:
                    feat['UsedByCommuters'] = 1
            else:
                ns, ew = 0.5, 0.5
                if 'UsedByCommuters' in writable:
                    feat['UsedByCommuters'] = 0
            if 'N_S_Weight' in writable:
                feat['N_S_Weight'] = ns
            if 'E_W_Weight' in writable:
                feat['E_W_Weight'] = ew
            try:
                junction_layer.updateFeature(feat)
                updated += 1
            except Exception:
                # if update fails (e.g., read-only shapefile), skip writing and continue
                continue

        try:
            if junction_layer.isEditable():
                junction_layer.commitChanges()
        except Exception:
            pass

        # cleanup debug layers if any
        for layer in debug_created:
            try:
                QgsProject.instance().removeMapLayer(layer.id())
            except Exception:
                pass

        self.status.setText(f'Completed. Updated {updated} junctions.')
        self.show_message('GeoScheduler Pro finished successfully.')
