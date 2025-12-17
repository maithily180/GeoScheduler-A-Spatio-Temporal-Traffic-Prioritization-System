from qgis.PyQt import QtWidgets, QtCore
from qgis.core import (
    QgsProject, QgsVectorLayer, QgsField, QgsFeature, QgsGeometry, QgsPointXY,
    QgsVectorFileWriter, QgsCoordinateTransform, QgsCoordinateTransformContext
)
from qgis.PyQt.QtCore import QVariant
import processing, tempfile, os, random

class GeoSchedulerProFinalStableTraffickersFixedV3Dialog(QtWidgets.QDialog):
    def __init__(self, iface):
        super().__init__(iface.mainWindow())
        self.iface = iface
        self.setWindowTitle('GeoScheduler Pro (Traffickers Fixed V3)')
        self.setMinimumWidth(760)
        layout = QtWidgets.QVBoxLayout()

        # selectors
        self.origin_combo = self.layer_selector('Origin Zones (polygon)')
        self.dest_combo   = self.layer_selector('Destination Zones (polygon)')
        self.road_combo   = self.layer_selector('Road Network (line)')
        self.junction_combo = self.layer_selector('Junctions (point)')

        for blk in (self.origin_combo, self.dest_combo, self.road_combo, self.junction_combo):
            layout.addLayout(blk['layout'])

        # params
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

        # time and debug
        time_row = QtWidgets.QHBoxLayout()
        time_row.addWidget(QtWidgets.QLabel('Time of Day:'))
        self.time_combo = QtWidgets.QComboBox()
        self.time_combo.addItems(['AM Peak','PM Peak','Off-Peak'])
        time_row.addWidget(self.time_combo)
        self.debug_check = QtWidgets.QCheckBox('Create debug centroid layers (visible)')
        time_row.addWidget(self.debug_check)
        layout.addLayout(time_row)

        # output path
        out_row = QtWidgets.QHBoxLayout()
        out_row.addWidget(QtWidgets.QLabel('Save GeoPackage to (leave blank = temp):'))
        self.out_edit = QtWidgets.QLineEdit()
        out_row.addWidget(self.out_edit)
        choose = QtWidgets.QPushButton('Browse')
        choose.clicked.connect(self.browse_output)
        out_row.addWidget(choose)
        layout.addLayout(out_row)

        self.run_btn = QtWidgets.QPushButton('Run and Create Visual Outputs')
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

    def browse_output(self):
        fn, _ = QtWidgets.QFileDialog.getSaveFileName(self, 'Save GeoPackage', '', 'GeoPackage (*.gpkg)')
        if fn:
            if not fn.lower().endswith('.gpkg'):
                fn += '.gpkg'
            self.out_edit.setText(fn)

    def show_message(self, text):
        QtWidgets.QMessageBox.information(self, 'GeoScheduler Pro (Traffickers Fixed V3)', text)

    def get_layer(self, name):
        items = QgsProject.instance().mapLayersByName(name)
        return items[0] if items else None

    def centroids_reproject(self, layer, target_crs):
        pts = []
        src_crs = layer.crs()
        transform = QgsCoordinateTransform(src_crs, target_crs, QgsProject.instance())
        for feat in layer.getFeatures():
            geom = feat.geometry()
            if not geom: continue
            try:
                c = geom.centroid().asPoint()
                t = transform.transform(c)
                pts.append(t)
            except Exception:
                continue
        return pts

    def km_reduce(self, pts, k):
        if len(pts) <= k: return pts
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
                    x = sum([p[0] for p in group])/len(group)
                    y = sum([p[1] for p in group])/len(group)
                    new.append((x,y))
                else:
                    new.append(random.choice(arr))
            centers = new
        return [QgsPointXY(c[0], c[1]) for c in centers]

    def to_qneat(self, pt, crs):
        return f"{pt.x()},{pt.y()} [{crs.authid()}]"

    def run_qneat_pair(self, road_layer, start, end):
        params = {
            'DEFAULT_DIRECTION':2, 'DEFAULT_SPEED':5, 'DIRECTION_FIELD':'',
            'END_POINT': end, 'ENTRY_COST_CALCULATION_METHOD':0,
            'INPUT': road_layer.source() if hasattr(road_layer,'source') else road_layer, 'OUTPUT':'memory:', 'SPEED_FIELD':'',
            'START_POINT': start, 'STRATEGY':0, 'TOLERANCE':0,
            'VALUE_BACKWARD':'', 'VALUE_BOTH':'', 'VALUE_FORWARD':''
        }
        try:
            res = processing.run('qneat3:shortestpathpointtopoint', params)
            out = res.get('OUTPUT') or list(res.values())[0]
            if isinstance(out, str) and os.path.exists(out):
                lyr = QgsVectorLayer(out, 'path', 'ogr')
                return lyr if lyr.isValid() else None
            if isinstance(out, QgsVectorLayer):
                return out
            return None
        except Exception:
            return None

    def aggregate_density(self, path_layers):
        counts={}
        for lyr in path_layers:
            for f in lyr.getFeatures():
                geom = f.geometry()
                if not geom: continue
                lines = geom.asMultiPolyline() if geom.isMultipart() else [geom.asPolyline()]
                for ln in lines:
                    for p in ln:
                        key=(round(p.x(),6), round(p.y(),6))
                        counts[key]=counts.get(key,0)+1
        maxc = max(counts.values()) if counts else 1
        return {k: v/maxc for k,v in counts.items()}

    def write_gpkg_layer(self, layer, gpkg_path, layer_name):
        # Use writeAsVectorFormatV3 for QGIS 3.40+
        opts = QgsVectorFileWriter.SaveVectorOptions()
        opts.driverName = 'GPKG'
        opts.layerName = layer_name
        opts.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer
        ctx = QgsCoordinateTransformContext()
        return QgsVectorFileWriter.writeAsVectorFormatV3(layer, gpkg_path, ctx, opts)

    def run_model(self):
        origin = self.get_layer(self.origin_combo['combo'].currentText())
        dest = self.get_layer(self.dest_combo['combo'].currentText())
        road = self.get_layer(self.road_combo['combo'].currentText())
        jun = self.get_layer(self.junction_combo['combo'].currentText())
        if not all([origin,dest,road,jun]):
            self.show_message('Missing layers'); return

        road_crs = road.crs()
        orig_pts = self.centroids_reproject(origin, road_crs)
        dest_pts = self.centroids_reproject(dest, road_crs)
        if not orig_pts or not dest_pts:
            self.show_message('No centroids found'); return

        m = self.max_spin.value()
        if len(orig_pts)>m: orig_pts=self.km_reduce(orig_pts,m)
        if len(dest_pts)>m: dest_pts=self.km_reduce(dest_pts,m)

        paths = []
        total = len(orig_pts)*len(dest_pts)
        c=0
        for o in orig_pts:
            for d in dest_pts:
                c+=1
                self.status.setText(f'Routing {c}/{total}'); QtCore.QCoreApplication.processEvents()
                s = self.to_qneat(o, road_crs); e = self.to_qneat(d, road_crs)
                p = self.run_qneat_pair(road, s, e)
                if p: paths.append(p)

        if not paths:
            self.show_message('No paths computed'); return

        density = self.aggregate_density(paths)
        thresh = self.density.value()

        # determine output path
        out_gpkg = self.out_edit.text().strip() or os.path.join(tempfile.gettempdir(), 'GeoScheduler_Output_v3.gpkg')

        # create OD routes layer by merging path geometries into a memory layer
        od_layer = QgsVectorLayer(f'LineString?crs={road_crs.authid()}', 'GeoScheduler_OD_Routes', 'memory')
        od_dp = od_layer.dataProvider()
        od_dp.addAttributes([QgsField('route_id', QVariant.Int)])
        od_layer.updateFields()
        rid = 1
        for p in paths:
            for feat in p.getFeatures():
                geom = feat.geometry()
                nf = QgsFeature(od_layer.fields())
                nf.setGeometry(geom)
                nf['route_id'] = rid
                od_dp.addFeature(nf)
                rid += 1
        od_layer.updateExtents()

        # create density points layer (memory)
        pts_layer = QgsVectorLayer(f'Point?crs={road_crs.authid()}&field=density:double', 'GeoScheduler_Density_Points', 'memory')
        prov = pts_layer.dataProvider()
        feats = []
        for (x,y),val in density.items():
            f = QgsFeature(pts_layer.fields())
            f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(x,y)))
            f['density'] = float(val)
            feats.append(f)
        prov.addFeatures(feats); pts_layer.updateExtents()

        # create junctions_weighted (memory) with new field names
        jun_out = QgsVectorLayer(f'Point?crs={road_crs.authid()}', 'junctions_weighted', 'memory')
        pprov = jun_out.dataProvider()
        pprov.addAttributes([QgsField('UsedByComm',QVariant.Int), QgsField('Corridor_Weight',QVariant.Double), QgsField('CrossTraffic_Weight',QVariant.Double)])
        jun_out.updateFields()
        feats2 = []
        for f in jun.getFeatures():
            g = f.geometry()
            if not g: continue
            pt = g.asPoint()
            key = (round(pt.x(),6), round(pt.y(),6))
            dens = density.get(key, 0.0)
            if dens >= thresh:
                used = 1
                if self.time_combo.currentText() == 'AM Peak':
                    cw, xw = 0.75, 0.25
                elif self.time_combo.currentText() == 'PM Peak':
                    cw, xw = 0.75, 0.25
                else:
                    cw, xw = 0.5, 0.5
            else:
                used = 0; cw, xw = 0.5, 0.5
            nf = QgsFeature(jun_out.fields())
            nf.setGeometry(QgsGeometry.fromPointXY(pt))
            nf['UsedByComm'] = int(used)
            nf['Corridor_Weight'] = float(cw)
            nf['CrossTraffic_Weight'] = float(xw)
            feats2.append(nf)
        pprov.addFeatures(feats2); jun_out.updateExtents()

        # write layers to GeoPackage (overwrite mode)
        try:
            # Overwrite entire gpkg by creating/truncating layers with CreateOrOverwriteLayer option
            self.write_gpkg_layer(od_layer, out_gpkg, 'GeoScheduler_OD_Routes')
            self.write_gpkg_layer(pts_layer, out_gpkg, 'GeoScheduler_Density_Points')
            self.write_gpkg_layer(jun_out, out_gpkg, 'junctions_weighted')
        except Exception as e:
            # final fallback: try legacy writer without options
            QgsVectorFileWriter.writeAsVectorFormat(od_layer, out_gpkg, 'utf-8', QgsCoordinateTransformContext(), 'GPKG')
            QgsVectorFileWriter.writeAsVectorFormat(pts_layer, out_gpkg, 'utf-8', QgsCoordinateTransformContext(), 'GPKG')
            QgsVectorFileWriter.writeAsVectorFormat(jun_out, out_gpkg, 'utf-8', QgsCoordinateTransformContext(), 'GPKG')

        # add layers and apply simple styling
        QgsProject.instance().addMapLayer(jun_out)
        QgsProject.instance().addMapLayer(pts_layer)
        try:
            od_loaded = QgsVectorLayer(out_gpkg + '|layername=GeoScheduler_OD_Routes', 'GeoScheduler_OD_Routes', 'ogr')
            if od_loaded.isValid(): QgsProject.instance().addMapLayer(od_loaded)
        except Exception:
            pass

        self.status.setText(f'Completed. Outputs written to {out_gpkg}')
        self.show_message(f'Completed. GeoPackage created at: {out_gpkg}')
