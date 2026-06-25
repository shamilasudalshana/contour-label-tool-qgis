"""
contour_label_dialog.py
========================
A PyQGIS dialog front end for the Contour Label Placer tool.
Paste this entire file into the QGIS Python Console editor and press Run,
or load it via Plugins → Python Console → Show Editor → Open File.

No installation required — the dialog opens immediately.

Author : HG Nord – Hydro-Geologie-Nord PartGmbB
License: MIT
"""

from qgis.core import (
    QgsProject, QgsGeometry, QgsPointXY,
    QgsField, QgsWkbTypes
)
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QComboBox, QPushButton, QGroupBox,
    QTextEdit, QSizePolicy, QFrame, QMessageBox,
    QProgressBar
)
from qgis.PyQt.QtCore import QVariant, Qt, QThread, pyqtSignal
from qgis.PyQt.QtGui import QFont, QColor, QPalette
import math


# ---------------------------------------------------------------------------
# Field name constants  (≤10 chars — Shapefile-safe)
# ---------------------------------------------------------------------------
FIELD_X   = "lbl_x"
FIELD_Y   = "lbl_y"
FIELD_ROT = "lbl_rot"


# ---------------------------------------------------------------------------
# Core placement logic (same as contour_label_placer.py)
# ---------------------------------------------------------------------------
def run_placement(contour_layer, ref_layer, elevation_field,
                  rotation_mode, uphill_direction, log_fn):
    """
    Run label placement and write results to the contour layer.
    log_fn(msg) is called to emit progress messages.
    Returns (placed, skipped) counts.
    """

    # ── Validate elevation field ────────────────────────────────────
    fields = contour_layer.fields()
    if elevation_field:
        if fields.indexOf(elevation_field) == -1:
            available = [f.name() for f in fields]
            log_fn(f"ERROR: Elevation field '{elevation_field}' not found.\n"
                   f"  Available: {available}")
            return None, None
        log_fn(f"✓ Elevation field '{elevation_field}' found.")

    # ── Create label fields if missing ──────────────────────────────
    fields_to_create = []
    for fname, ftype in [(FIELD_X,   QVariant.Double),
                         (FIELD_Y,   QVariant.Double),
                         (FIELD_ROT, QVariant.Double)]:
        if fields.indexOf(fname) == -1:
            fields_to_create.append(QgsField(fname, ftype))

    if fields_to_create:
        contour_layer.startEditing()
        contour_layer.dataProvider().addAttributes(fields_to_create)
        contour_layer.updateFields()
        contour_layer.commitChanges()
        log_fn(f"✓ Created fields: {[f.name() for f in fields_to_create]}")
    else:
        log_fn(f"✓ Fields {FIELD_X}, {FIELD_Y}, {FIELD_ROT} already exist — reusing.")

    fields   = contour_layer.fields()
    idx_x    = fields.indexOf(FIELD_X)
    idx_y    = fields.indexOf(FIELD_Y)
    idx_rot  = fields.indexOf(FIELD_ROT)
    idx_elev = fields.indexOf(elevation_field) if elevation_field else None

    # ── Read reference line ─────────────────────────────────────────
    ref_features = list(ref_layer.getFeatures())
    if not ref_features:
        log_fn("ERROR: Reference line layer has no features.")
        return None, None

    ref_geom = ref_features[0].geometry()
    ref_line = (ref_geom.asPolyline()
                if not ref_geom.isMultipart()
                else ref_geom.asMultiPolyline()[0])

    slope_start = QgsPointXY(ref_line[0])
    slope_end   = QgsPointXY(ref_line[-1])

    ref_dx = slope_end.x() - slope_start.x()
    ref_dy = slope_end.y() - slope_start.y()
    ref_angle_math     = math.degrees(math.atan2(ref_dy, ref_dx))
    ref_label_rotation = (-ref_angle_math + 90) % 360

    # ── Elevation-based direction detection ─────────────────────────
    elev_at_start = None
    elev_at_end   = None
    elev_flip     = False

    if uphill_direction in ("low_to_high", "high_to_low") and idx_elev is not None:
        start_geom     = QgsGeometry.fromPointXY(slope_start)
        end_geom       = QgsGeometry.fromPointXY(slope_end)
        min_dist_start = float('inf')
        min_dist_end   = float('inf')

        for feat in contour_layer.getFeatures():
            geom = feat.geometry()
            elev = feat.attribute(elevation_field)
            if elev is None:
                continue
            d_start = geom.distance(start_geom)
            d_end   = geom.distance(end_geom)
            if d_start < min_dist_start:
                min_dist_start = d_start
                elev_at_start  = elev
            if d_end < min_dist_end:
                min_dist_end = d_end
                elev_at_end  = elev

        if elev_at_start is None or elev_at_end is None:
            log_fn("WARNING: Could not sample elevation — falling back to 'reference' direction.")
            uphill_direction = "reference"
        else:
            log_fn(f"  Elevation at START : {elev_at_start}")
            log_fn(f"  Elevation at END   : {elev_at_end}")

            if uphill_direction == "low_to_high":
                elev_flip = elev_at_end < elev_at_start
            else:
                elev_flip = elev_at_end > elev_at_start

            log_fn(f"  Direction flip applied: {elev_flip}")

    # ── Main loop ───────────────────────────────────────────────────
    contour_layer.startEditing()
    placed_count  = 0
    skipped_count = 0

    for contour_feat in contour_layer.getFeatures():
        contour_geom = contour_feat.geometry()
        intersection = contour_geom.intersection(ref_geom)

        if intersection.isEmpty():
            skipped_count += 1
            continue

        if intersection.isMultipart():
            pts = intersection.asMultiPoint()
            pt  = pts[0] if pts else None
        else:
            pt = intersection.asPoint()

        if pt is None:
            skipped_count += 1
            continue

        label_pos = QgsPointXY(pt)

        # Uphill vector
        if uphill_direction == "reference":
            to_uphill_x = slope_end.x() - label_pos.x()
            to_uphill_y = slope_end.y() - label_pos.y()
        else:
            if elev_flip:
                to_uphill_x = slope_start.x() - label_pos.x()
                to_uphill_y = slope_start.y() - label_pos.y()
            else:
                to_uphill_x = slope_end.x() - label_pos.x()
                to_uphill_y = slope_end.y() - label_pos.y()

        # Rotation
        if rotation_mode == "contour":
            vertices = list(contour_geom.vertices())
            min_dist = float('inf')
            nearest_seg_idx = 0
            for i in range(len(vertices) - 1):
                seg = QgsGeometry.fromPolylineXY([
                    QgsPointXY(vertices[i]),
                    QgsPointXY(vertices[i + 1])
                ])
                dist = seg.distance(QgsGeometry.fromPointXY(label_pos))
                if dist < min_dist:
                    min_dist = dist
                    nearest_seg_idx = i

            v1 = vertices[nearest_seg_idx]
            v2 = vertices[nearest_seg_idx + 1]
            dx = v2.x() - v1.x()
            dy = v2.y() - v1.y()

            label_rotation = (-math.degrees(math.atan2(dy, dx))) % 360
            label_up_x = -dy
            label_up_y =  dx
            dot = label_up_x * to_uphill_x + label_up_y * to_uphill_y
            if dot < 0:
                label_rotation = (label_rotation + 180) % 360

        else:  # reference
            label_rotation = ref_label_rotation
            label_up_x = ref_dx
            label_up_y = ref_dy
            dot = label_up_x * to_uphill_x + label_up_y * to_uphill_y
            if dot < 0:
                label_rotation = (label_rotation + 180) % 360

        contour_layer.changeAttributeValue(contour_feat.id(), idx_x,   label_pos.x())
        contour_layer.changeAttributeValue(contour_feat.id(), idx_y,   label_pos.y())
        contour_layer.changeAttributeValue(contour_feat.id(), idx_rot, label_rotation)
        placed_count += 1

    contour_layer.commitChanges()
    contour_layer.triggerRepaint()

    return placed_count, skipped_count


# ---------------------------------------------------------------------------
# Dialog UI
# ---------------------------------------------------------------------------
class ContourLabelDialog(QDialog):

    # ── Colour palette (blue/teal — matches hydrogeology conventions) ──
    CLR_BG       = "#F4F7FA"   # very light blue-grey background
    CLR_PANEL    = "#FFFFFF"   # white card panels
    CLR_ACCENT   = "#1A6E9E"   # HG Nord blue
    CLR_ACCENT2  = "#2A9D8F"   # teal — water association
    CLR_TEXT     = "#1C2B3A"   # near-black
    CLR_MUTED    = "#6B7C8D"   # secondary text
    CLR_SUCCESS  = "#2A9D8F"
    CLR_ERROR    = "#C0392B"
    CLR_LOG_BG   = "#1C2B3A"   # dark log panel
    CLR_LOG_TEXT = "#A8D8EA"   # light cyan log text

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Contour Label Placer — HG Nord")
        self.setMinimumWidth(520)
        self.setMinimumHeight(640)
        self._build_ui()
        self._populate_layers()
        self._on_layer_changed()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self):
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {self.CLR_BG};
                color: {self.CLR_TEXT};
                font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
                font-size: 13px;
            }}
            QGroupBox {{
                background-color: {self.CLR_PANEL};
                border: 1px solid #D0DCE8;
                border-radius: 6px;
                margin-top: 10px;
                padding: 12px 14px 10px 14px;
                font-weight: 600;
                color: {self.CLR_ACCENT};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 4px;
                background-color: {self.CLR_PANEL};
            }}
            QLabel {{
                color: {self.CLR_TEXT};
            }}
            QComboBox {{
                background-color: {self.CLR_PANEL};
                border: 1px solid #C0CDD8;
                border-radius: 4px;
                padding: 5px 8px;
                min-height: 24px;
                color: {self.CLR_TEXT};
                selection-background-color: {self.CLR_ACCENT};
            }}
            QComboBox:hover {{
                border-color: {self.CLR_ACCENT};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 22px;
            }}
            QPushButton#runBtn {{
                background-color: {self.CLR_ACCENT};
                color: white;
                border: none;
                border-radius: 5px;
                padding: 10px 0;
                font-size: 14px;
                font-weight: 700;
                letter-spacing: 0.5px;
            }}
            QPushButton#runBtn:hover {{
                background-color: #15587F;
            }}
            QPushButton#runBtn:pressed {{
                background-color: #0F3F5E;
            }}
            QPushButton#runBtn:disabled {{
                background-color: #9DB3C4;
            }}
            QPushButton#refreshBtn {{
                background-color: transparent;
                border: 1px solid {self.CLR_ACCENT};
                border-radius: 4px;
                color: {self.CLR_ACCENT};
                padding: 4px 10px;
                font-size: 12px;
            }}
            QPushButton#refreshBtn:hover {{
                background-color: #E8F0F7;
            }}
            QTextEdit {{
                background-color: {self.CLR_LOG_BG};
                color: {self.CLR_LOG_TEXT};
                border: none;
                border-radius: 4px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 12px;
                padding: 6px;
            }}
            QProgressBar {{
                background-color: #D0DCE8;
                border: none;
                border-radius: 3px;
                height: 6px;
                text-align: center;
            }}
            QProgressBar::chunk {{
                background-color: {self.CLR_ACCENT2};
                border-radius: 3px;
            }}
        """)

        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(16, 16, 16, 16)

        # ── Header ────────────────────────────────────────────────────
        header = QLabel("Contour Label Placer")
        header.setStyleSheet(f"""
            font-size: 18px;
            font-weight: 700;
            color: {self.CLR_ACCENT};
            padding-bottom: 2px;
        """)
        sub = QLabel("Automatically place and rotate isoline labels along a reference line.")
        sub.setStyleSheet(f"color: {self.CLR_MUTED}; font-size: 12px;")
        sub.setWordWrap(True)
        root.addWidget(header)
        root.addWidget(sub)

        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setStyleSheet(f"color: #D0DCE8;")
        root.addWidget(divider)

        # ── Layer selection ───────────────────────────────────────────
        layer_group = QGroupBox("1 · Select Layers")
        layer_form  = QFormLayout(layer_group)
        layer_form.setSpacing(8)

        # Refresh button row
        refresh_row = QHBoxLayout()
        refresh_btn = QPushButton("↺  Refresh layer list")
        refresh_btn.setObjectName("refreshBtn")
        refresh_btn.setCursor(Qt.PointingHandCursor)
        refresh_btn.clicked.connect(self._populate_layers)
        refresh_row.addStretch()
        refresh_row.addWidget(refresh_btn)
        layer_form.addRow(refresh_row)

        self.contour_combo = QComboBox()
        self.contour_combo.setToolTip("The polyline layer containing your contour/isoline features.")
        self.contour_combo.currentIndexChanged.connect(self._on_layer_changed)
        layer_form.addRow(QLabel("Contour layer:"), self.contour_combo)

        self.ref_combo = QComboBox()
        self.ref_combo.setToolTip(
            "A line layer you drew crossing the contours to be labelled.\n"
            "Draw from the downhill end toward the uphill end."
        )
        layer_form.addRow(QLabel("Reference line:"), self.ref_combo)

        root.addWidget(layer_group)

        # ── Field selection ───────────────────────────────────────────
        field_group = QGroupBox("2 · Elevation Field")
        field_form  = QFormLayout(field_group)
        field_form.setSpacing(8)

        self.elev_combo = QComboBox()
        self.elev_combo.setToolTip(
            "Attribute field storing the elevation value of each contour.\n"
            "Required when Label Direction is 'Low → High' or 'High → Low'."
        )
        self.elev_combo.insertItem(0, "(none)", None)
        field_form.addRow(QLabel("Elevation field:"), self.elev_combo)

        root.addWidget(field_group)

        # ── Options ───────────────────────────────────────────────────
        opt_group = QGroupBox("3 · Options")
        opt_form  = QFormLayout(opt_group)
        opt_form.setSpacing(8)

        self.rotation_combo = QComboBox()
        self.rotation_combo.addItem("Follow contour tangent  (each label differs)", "contour")
        self.rotation_combo.addItem("Follow reference line   (all labels same angle)", "reference")
        self.rotation_combo.setToolTip(
            "Contour tangent: labels align individually to each contour.\n"
            "Reference line: all labels share the same angle — cleaner look."
        )
        opt_form.addRow(QLabel("Rotation mode:"), self.rotation_combo)

        self.direction_combo = QComboBox()
        self.direction_combo.addItem("Auto: Low → High elevation  (recommended)", "low_to_high")
        self.direction_combo.addItem("Auto: High → Low elevation", "high_to_low")
        self.direction_combo.addItem("Manual: reference line draw direction", "reference")
        self.direction_combo.setToolTip(
            "Low → High: label tops face uphill, detected from elevation field.\n"
            "High → Low: label tops face downhill.\n"
            "Manual: uphill = the direction you drew the reference line (start → end)."
        )
        opt_form.addRow(QLabel("Label direction:"), self.direction_combo)

        root.addWidget(opt_group)

        # ── Run button + progress ─────────────────────────────────────
        self.run_btn = QPushButton("▶   Place Labels")
        self.run_btn.setObjectName("runBtn")
        self.run_btn.setCursor(Qt.PointingHandCursor)
        self.run_btn.setMinimumHeight(44)
        self.run_btn.clicked.connect(self._run)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)   # indeterminate
        self.progress.setVisible(False)
        self.progress.setFixedHeight(6)

        root.addWidget(self.run_btn)
        root.addWidget(self.progress)

        # ── Log panel ─────────────────────────────────────────────────
        log_label = QLabel("Output log")
        log_label.setStyleSheet(f"color: {self.CLR_MUTED}; font-size: 11px; font-weight: 600;")
        root.addWidget(log_label)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(160)
        self.log.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        root.addWidget(self.log)

        # ── Footer hint ───────────────────────────────────────────────
        hint = QLabel(
            "⚠  After first run: Layer Properties → Labels → Placement → Data Defined\n"
            f"   X Coordinate → {FIELD_X}  |  Y Coordinate → {FIELD_Y}  |  Rotation → {FIELD_ROT}"
        )
        hint.setStyleSheet(f"""
            background-color: #FFF8E1;
            border: 1px solid #F0C040;
            border-radius: 4px;
            color: #5D4037;
            font-size: 11px;
            padding: 7px 10px;
        """)
        hint.setWordWrap(True)
        root.addWidget(hint)

    # ------------------------------------------------------------------
    # Layer / field population
    # ------------------------------------------------------------------
    def _populate_layers(self):
        """Populate the layer dropdowns from the current QGIS project."""
        project = QgsProject.instance()
        all_layers = list(project.mapLayers().values())

        line_layers = [
            l for l in all_layers
            if hasattr(l, 'geometryType') and
               l.geometryType() == QgsWkbTypes.LineGeometry
        ]

        # Remember current selections
        prev_contour = self.contour_combo.currentData()
        prev_ref     = self.ref_combo.currentData()

        self.contour_combo.blockSignals(True)
        self.ref_combo.blockSignals(True)

        self.contour_combo.clear()
        self.ref_combo.clear()

        for lyr in line_layers:
            self.contour_combo.addItem(lyr.name(), lyr.id())
            self.ref_combo.addItem(lyr.name(), lyr.id())

        # Restore previous selections where possible
        for combo, prev in [(self.contour_combo, prev_contour),
                            (self.ref_combo, prev_ref)]:
            if prev:
                idx = combo.findData(prev)
                if idx >= 0:
                    combo.setCurrentIndex(idx)

        self.contour_combo.blockSignals(False)
        self.ref_combo.blockSignals(False)

        self._on_layer_changed()
        self._log(f"Layer list refreshed — {len(line_layers)} line layer(s) found.")

    def _on_layer_changed(self):
        """Refresh the elevation field combo when the contour layer changes."""
        self.elev_combo.blockSignals(True)
        self.elev_combo.clear()
        self.elev_combo.addItem("(none — required for Auto modes)", None)

        layer_id = self.contour_combo.currentData()
        if layer_id:
            layer = QgsProject.instance().mapLayer(layer_id)
            if layer:
                for field in layer.fields():
                    t = field.type()
                    if t in (QVariant.Double, QVariant.Int, QVariant.LongLong,
                             QVariant.UInt, QVariant.ULongLong):
                        self.elev_combo.addItem(field.name(), field.name())

        self.elev_combo.blockSignals(False)

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------
    def _run(self):
        project = QgsProject.instance()

        contour_id = self.contour_combo.currentData()
        ref_id     = self.ref_combo.currentData()

        if not contour_id or not ref_id:
            QMessageBox.warning(self, "Missing layer", "Please select both layers.")
            return
        if contour_id == ref_id:
            QMessageBox.warning(self, "Same layer",
                                "Contour layer and reference line must be different layers.")
            return

        contour_layer = project.mapLayer(contour_id)
        ref_layer     = project.mapLayer(ref_id)
        elevation_field  = self.elev_combo.currentData()
        rotation_mode    = self.rotation_combo.currentData()
        uphill_direction = self.direction_combo.currentData()

        if uphill_direction in ("low_to_high", "high_to_low") and not elevation_field:
            QMessageBox.warning(
                self, "Elevation field required",
                "The selected label direction needs an elevation field.\n"
                "Please choose one in section 2, or switch direction to 'Manual'."
            )
            return

        self.log.clear()
        self._log("Starting label placement…")
        self._log(f"  Contour layer   : {contour_layer.name()}")
        self._log(f"  Reference line  : {ref_layer.name()}")
        self._log(f"  Elevation field : {elevation_field or '(none)'}")
        self._log(f"  Rotation mode   : {rotation_mode}")
        self._log(f"  Label direction : {uphill_direction}")
        self._log("")

        self.run_btn.setEnabled(False)
        self.progress.setVisible(True)

        placed, skipped = run_placement(
            contour_layer, ref_layer, elevation_field,
            rotation_mode, uphill_direction, self._log
        )

        self.progress.setVisible(False)
        self.run_btn.setEnabled(True)

        if placed is None:
            self._log("\n✗  Placement failed — see errors above.", error=True)
            return

        self._log("")
        self._log("=" * 44)
        self._log(f"  Labels placed : {placed}")
        self._log(f"  Skipped       : {skipped}  (no intersection)")
        self._log("=" * 44)
        self._log("")
        self._log("✓ Done! Now connect the fields in QGIS:")
        self._log(f"  Layer Properties → Labels → Placement")
        self._log(f"  → Data Defined X  :  {FIELD_X}")
        self._log(f"  → Data Defined Y  :  {FIELD_Y}")
        self._log(f"  → Data Defined Rotation : {FIELD_ROT}")

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------
    def _log(self, msg: str, error: bool = False):
        colour = "#FF6B6B" if error else self.CLR_LOG_TEXT
        self.log.append(f'<span style="color:{colour};">{msg}</span>')
        self.log.verticalScrollBar().setValue(
            self.log.verticalScrollBar().maximum()
        )


# ---------------------------------------------------------------------------
# Launch
# ---------------------------------------------------------------------------
dialog = ContourLabelDialog()
dialog.show()
