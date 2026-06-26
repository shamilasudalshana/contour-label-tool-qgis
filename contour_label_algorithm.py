"""
contour_label_algorithm.py
===========================
QGIS Processing Toolbox algorithm for the Contour Label Placer.

Registers under:
    Processing Toolbox → HG Nord tools → Place contour labels

HOW TO LOAD (two options)
--------------------------
Option A — Temporary (current session only):
    1. Open QGIS Python Console  (Plugins → Python Console)
    2. Click Show Editor (pencil icon), open this file, press ▶ Run
    The algorithm appears in the Processing Toolbox immediately.

Option B — Permanent (survives QGIS restart):
    1. Find your QGIS scripts folder:
         Settings → User Profiles → Open Active Profile Folder
         → processing → scripts
    2. Copy this file there.
    3. In the Processing Toolbox click ⚙ → Scripts → Reload scripts
       (or restart QGIS).
    The algorithm will always be available under Scripts → HG Nord tools.

Author : HG Nord – Hydro-Geologie-Nord PartGmbB
License: MIT
"""

from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterVectorLayer,
    QgsProcessingParameterField,
    QgsProcessingParameterEnum,
    QgsProcessingParameterBoolean,
    QgsGeometry,
    QgsPointXY,
    QgsField,
    QgsFeatureRequest,
)
from qgis.PyQt.QtCore import QVariant, QCoreApplication
import math

# ---------------------------------------------------------------------------
# Field name constants  (≤10 chars — Shapefile-safe)
# ---------------------------------------------------------------------------
FIELD_X   = "lbl_x"
FIELD_Y   = "lbl_y"
FIELD_ROT = "lbl_rot"


# ---------------------------------------------------------------------------
# Algorithm class
# ---------------------------------------------------------------------------
class ContourLabelAlgorithm(QgsProcessingAlgorithm):

    # Parameter IDs
    CONTOUR_LAYER    = "CONTOUR_LAYER"
    REFERENCE_LAYER  = "REFERENCE_LAYER"
    USE_SELECTION    = "USE_SELECTION"
    ELEVATION_FIELD  = "ELEVATION_FIELD"
    ROTATION_MODE    = "ROTATION_MODE"
    UPHILL_DIRECTION = "UPHILL_DIRECTION"

    # --- Required metadata ---
    def name(self):        return "place_contour_labels"
    def displayName(self): return "Place contour labels"
    def group(self):       return "HG Nord tools"
    def groupId(self):     return "hgnord"

    def shortHelpString(self):
        return (
            "<b>Place contour labels</b><br><br>"
            "Automatically places and rotates contour/isoline labels along one "
            "or more reference lines, writing label positions and rotation "
            "angles into three attribute fields on the contour layer.<br><br>"

            "<b>Workflow:</b><br>"
            "1. Draw one or more reference lines in a temporary scratch layer "
            "(Layer → New Temporary Scratch Layer, geometry type: Line). "
            "Each line should cross the contours you want to label in that area. "
            "Draw from the downhill end toward the uphill end when using "
            "'Reference line draw direction'.<br>"
            "2. To process only specific lines: select them in the map canvas "
            "before running the tool, then tick <i>Use selected lines only</i>. "
            "This lets you work through a complex map area by area — draw all "
            "your reference lines first, then select and run one group at a time.<br>"
            "3. Run this tool and choose your layers and options.<br>"
            "4. After the first run, open <i>Layer Properties → Labels → "
            "Placement</i> and connect the Data Defined overrides (once only):<br>"
            "&nbsp;&nbsp;&nbsp;• X Coordinate &nbsp;→&nbsp; <code>lbl_x</code><br>"
            "&nbsp;&nbsp;&nbsp;• Y Coordinate &nbsp;→&nbsp; <code>lbl_y</code><br>"
            "&nbsp;&nbsp;&nbsp;• Rotation &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;→&nbsp; <code>lbl_rot</code><br><br>"

            "<b>Multiple reference lines:</b><br>"
            "When more than one line is used (all features or a selection), "
            "each line is processed independently with its own elevation "
            "detection. A contour intersected by two lines keeps the result "
            "from the last line that touches it, so design your lines to cover "
            "different parts of the map without overlapping.<br><br>"

            "<b>Rotation mode:</b><br>"
            "• <i>Contour tangent</i> — each label independently follows the "
            "local direction of its contour.<br>"
            "• <i>Reference line</i> — all labels for that line share the same "
            "angle. Gives a cleaner, more uniform look.<br><br>"

            "<b>Label direction:</b><br>"
            "• <i>Low → High (auto)</i> — the tool detects which end of each "
            "reference line is uphill from the elevation field. <b>Recommended.</b><br>"
            "• <i>High → Low (auto)</i> — same auto-detection; tops face downhill.<br>"
            "• <i>Reference line draw direction</i> — uphill = the direction "
            "you drew the line (first click → last click). No elevation field needed.<br><br>"

            "<b>Output fields written to the contour layer:</b><br>"
            "<code>lbl_x</code>, <code>lbl_y</code>, <code>lbl_rot</code> "
            "(created automatically if they do not exist). "
            "Field names are ≤ 10 characters for Shapefile compatibility.<br><br>"

            "No external Python packages required."
        )

    def tr(self, string):
        return QCoreApplication.translate("ContourLabelAlgorithm", string)

    def createInstance(self):
        return ContourLabelAlgorithm()

    # --- Parameters ---
    def initAlgorithm(self, config=None):

        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.CONTOUR_LAYER,
                self.tr("Contour layer"),
                types=[QgsProcessing.TypeVectorLine],
            )
        )

        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.REFERENCE_LAYER,
                self.tr("Reference line layer"),
                types=[QgsProcessing.TypeVectorLine],
            )
        )

        use_sel = QgsProcessingParameterBoolean(
            self.USE_SELECTION,
            self.tr("Use selected lines only"),
            defaultValue=False,
            optional=False,
        )
        use_sel.setHelp(
            "When ticked, only the lines currently selected in the reference "
            "line layer are used. Useful for processing one area of a complex "
            "map at a time: draw all reference lines first, then select a "
            "subset, tick this option, and run the tool."
        )
        self.addParameter(use_sel)

        self.addParameter(
            QgsProcessingParameterField(
                self.ELEVATION_FIELD,
                self.tr("Elevation field"),
                parentLayerParameterName=self.CONTOUR_LAYER,
                type=QgsProcessingParameterField.Numeric,
                optional=True,
            )
        )

        self.addParameter(
            QgsProcessingParameterEnum(
                self.ROTATION_MODE,
                self.tr("Rotation mode"),
                options=[
                    "Contour tangent  (each label follows its own contour)",
                    "Reference line   (all labels share the same angle)",
                ],
                defaultValue=0,
            )
        )

        self.addParameter(
            QgsProcessingParameterEnum(
                self.UPHILL_DIRECTION,
                self.tr("Label direction"),
                options=[
                    "Low → High elevation  (auto, recommended)",
                    "High → Low elevation  (auto)",
                    "Reference line draw direction  (manual)",
                ],
                defaultValue=0,
            )
        )

    # --- Execution ---
    def processAlgorithm(self, parameters, context, feedback):

        contour_layer   = self.parameterAsVectorLayer(parameters, self.CONTOUR_LAYER,    context)
        ref_layer       = self.parameterAsVectorLayer(parameters, self.REFERENCE_LAYER,   context)
        use_selection   = self.parameterAsBoolean(    parameters, self.USE_SELECTION,     context)
        elevation_field = self.parameterAsString(     parameters, self.ELEVATION_FIELD,   context) or None
        rotation_idx    = self.parameterAsEnum(       parameters, self.ROTATION_MODE,     context)
        direction_idx   = self.parameterAsEnum(       parameters, self.UPHILL_DIRECTION,  context)

        rotation_mode    = ["contour", "reference"][rotation_idx]
        uphill_direction = ["low_to_high", "high_to_low", "reference"][direction_idx]

        # ── Basic validation ─────────────────────────────────────────
        if uphill_direction in ("low_to_high", "high_to_low") and not elevation_field:
            feedback.reportError(
                "An elevation field is required when label direction is "
                "'Low → High' or 'High → Low'. "
                "Select an elevation field or switch to 'Reference line draw direction'.",
                fatalError=True,
            )
            return {}

        if contour_layer.id() == ref_layer.id():
            feedback.reportError(
                "Contour layer and reference line layer must be different layers.",
                fatalError=True,
            )
            return {}

        # ── Collect reference lines ───────────────────────────────────
        if use_selection:
            selected_ids = ref_layer.selectedFeatureIds()
            if not selected_ids:
                feedback.reportError(
                    "'Use selected lines only' is ticked but no features are "
                    "selected in the reference line layer. "
                    "Select one or more lines in the map canvas and run again.",
                    fatalError=True,
                )
                return {}
            request      = QgsFeatureRequest().setFilterFids(selected_ids)
            ref_features = list(ref_layer.getFeatures(request))
            feedback.pushInfo(
                f"✓ Using {len(ref_features)} selected reference line(s)."
            )
        else:
            ref_features = list(ref_layer.getFeatures())
            if not ref_features:
                feedback.reportError(
                    "Reference line layer has no features.", fatalError=True
                )
                return {}
            feedback.pushInfo(
                f"✓ Using all {len(ref_features)} reference line(s) in the layer."
            )

        # ── Elevation field check ─────────────────────────────────────
        fields = contour_layer.fields()
        if elevation_field and fields.indexOf(elevation_field) == -1:
            feedback.reportError(
                f"Elevation field '{elevation_field}' not found in contour layer.",
                fatalError=True,
            )
            return {}
        if elevation_field:
            feedback.pushInfo(f"✓ Elevation field '{elevation_field}' found.")

        # ── Create label fields if missing ────────────────────────────
        fields_to_create = []
        for fname, ftype in [(FIELD_X, QVariant.Double),
                             (FIELD_Y, QVariant.Double),
                             (FIELD_ROT, QVariant.Double)]:
            if fields.indexOf(fname) == -1:
                fields_to_create.append(QgsField(fname, ftype))

        if fields_to_create:
            contour_layer.startEditing()
            contour_layer.dataProvider().addAttributes(fields_to_create)
            contour_layer.updateFields()
            contour_layer.commitChanges()
            feedback.pushInfo(
                f"✓ Created fields: {[f.name() for f in fields_to_create]}"
            )
        else:
            feedback.pushInfo(
                f"✓ Fields {FIELD_X}, {FIELD_Y}, {FIELD_ROT} already exist — reusing."
            )

        fields   = contour_layer.fields()
        idx_x    = fields.indexOf(FIELD_X)
        idx_y    = fields.indexOf(FIELD_Y)
        idx_rot  = fields.indexOf(FIELD_ROT)
        idx_elev = fields.indexOf(elevation_field) if elevation_field else None

        total_features    = contour_layer.featureCount()
        total_ref         = len(ref_features)
        grand_placed      = 0
        grand_skipped     = 0

        # ── Process each reference line independently ─────────────────
        contour_layer.startEditing()

        for ref_idx, ref_feat in enumerate(ref_features):
            if feedback.isCanceled():
                contour_layer.rollBack()
                return {}

            ref_geom = ref_feat.geometry()
            ref_line = (ref_geom.asPolyline()
                        if not ref_geom.isMultipart()
                        else ref_geom.asMultiPolyline()[0])

            slope_start = QgsPointXY(ref_line[0])
            slope_end   = QgsPointXY(ref_line[-1])
            ref_dx      = slope_end.x() - slope_start.x()
            ref_dy      = slope_end.y() - slope_start.y()
            ref_label_rotation = (
                -math.degrees(math.atan2(ref_dy, ref_dx)) + 90
            ) % 360

            ref_label = (
                f"line {ref_idx + 1}/{total_ref}"
                + (f" (id {ref_feat.id()})" if total_ref > 1 else "")
            )
            feedback.pushInfo("")
            feedback.pushInfo(f"── Reference {ref_label} ──────────────────")

            # Elevation-based direction detection for this line
            elev_at_start    = None
            elev_at_end      = None
            elev_flip        = False
            this_direction   = uphill_direction   # may be overridden per-line

            if this_direction in ("low_to_high", "high_to_low") and idx_elev is not None:
                start_geom     = QgsGeometry.fromPointXY(slope_start)
                end_geom       = QgsGeometry.fromPointXY(slope_end)
                min_dist_start = float('inf')
                min_dist_end   = float('inf')

                for feat in contour_layer.getFeatures():
                    if feedback.isCanceled():
                        contour_layer.rollBack()
                        return {}
                    geom = feat.geometry()
                    elev = feat.attribute(elevation_field)
                    if elev is None:
                        continue
                    d_s = geom.distance(start_geom)
                    d_e = geom.distance(end_geom)
                    if d_s < min_dist_start:
                        min_dist_start = d_s
                        elev_at_start  = elev
                    if d_e < min_dist_end:
                        min_dist_end = d_e
                        elev_at_end  = elev

                if elev_at_start is None or elev_at_end is None:
                    feedback.pushWarning(
                        "  Could not sample elevation — falling back to "
                        "reference line draw direction for this line."
                    )
                    this_direction = "reference"
                else:
                    feedback.pushInfo(f"  Elevation at START : {elev_at_start}")
                    feedback.pushInfo(f"  Elevation at END   : {elev_at_end}")
                    elev_flip = (
                        (elev_at_end < elev_at_start)
                        if this_direction == "low_to_high"
                        else (elev_at_end > elev_at_start)
                    )
                    feedback.pushInfo(f"  Direction flip applied: {elev_flip}")

            # Intersect contours against this reference line
            placed_this  = 0
            skipped_this = 0

            for i, contour_feat in enumerate(contour_layer.getFeatures()):
                if feedback.isCanceled():
                    contour_layer.rollBack()
                    return {}

                # Overall progress across all reference lines
                overall = int(
                    ((ref_idx + i / max(total_features, 1)) / total_ref) * 100
                )
                feedback.setProgress(overall)

                contour_geom = contour_feat.geometry()
                intersection = contour_geom.intersection(ref_geom)

                if intersection.isEmpty():
                    skipped_this += 1
                    continue

                pt = (
                    intersection.asMultiPoint()[0]
                    if intersection.isMultipart()
                    else intersection.asPoint()
                )
                if pt is None:
                    skipped_this += 1
                    continue

                label_pos = QgsPointXY(pt)

                # Uphill vector for this line
                if this_direction == "reference" or not elev_flip:
                    to_uphill_x = slope_end.x() - label_pos.x()
                    to_uphill_y = slope_end.y() - label_pos.y()
                else:
                    to_uphill_x = slope_start.x() - label_pos.x()
                    to_uphill_y = slope_start.y() - label_pos.y()

                if this_direction == "reference":
                    to_uphill_x = slope_end.x() - label_pos.x()
                    to_uphill_y = slope_end.y() - label_pos.y()

                # Rotation
                if rotation_mode == "contour":
                    vertices = list(contour_geom.vertices())
                    min_dist = float('inf')
                    nearest  = 0
                    for j in range(len(vertices) - 1):
                        seg  = QgsGeometry.fromPolylineXY(
                            [QgsPointXY(vertices[j]), QgsPointXY(vertices[j + 1])]
                        )
                        dist = seg.distance(QgsGeometry.fromPointXY(label_pos))
                        if dist < min_dist:
                            min_dist = dist
                            nearest  = j
                    dx = vertices[nearest + 1].x() - vertices[nearest].x()
                    dy = vertices[nearest + 1].y() - vertices[nearest].y()
                    label_rotation = (-math.degrees(math.atan2(dy, dx))) % 360
                    if (-dy) * to_uphill_x + dx * to_uphill_y < 0:
                        label_rotation = (label_rotation + 180) % 360
                else:
                    label_rotation = ref_label_rotation
                    if ref_dx * to_uphill_x + ref_dy * to_uphill_y < 0:
                        label_rotation = (label_rotation + 180) % 360

                contour_layer.changeAttributeValue(
                    contour_feat.id(), idx_x, label_pos.x()
                )
                contour_layer.changeAttributeValue(
                    contour_feat.id(), idx_y, label_pos.y()
                )
                contour_layer.changeAttributeValue(
                    contour_feat.id(), idx_rot, label_rotation
                )
                placed_this += 1

            feedback.pushInfo(
                f"  Labels placed: {placed_this}  |  "
                f"Skipped (no intersection): {skipped_this}"
            )
            grand_placed  += placed_this
            grand_skipped += skipped_this

        contour_layer.commitChanges()
        contour_layer.triggerRepaint()
        feedback.setProgress(100)

        # ── Summary ───────────────────────────────────────────────────
        feedback.pushInfo("")
        feedback.pushInfo("=" * 50)
        feedback.pushInfo(f"  Reference lines processed : {total_ref}")
        feedback.pushInfo(f"  Total labels placed       : {grand_placed}")
        feedback.pushInfo(f"  Total skipped             : {grand_skipped}")
        feedback.pushInfo("=" * 50)
        feedback.pushInfo("")
        feedback.pushInfo("NEXT STEP — connect fields to label data-defined overrides:")
        feedback.pushInfo("  Layer Properties → Labels → Placement → Data Defined:")
        feedback.pushInfo(f"    X Coordinate  →  {FIELD_X}")
        feedback.pushInfo(f"    Y Coordinate  →  {FIELD_Y}")
        feedback.pushInfo(f"    Rotation      →  {FIELD_ROT}")

        return {}


# ---------------------------------------------------------------------------
# Registration — executed when the file is run in the Python Console
# ---------------------------------------------------------------------------
from qgis.core import QgsApplication

try:
    from processing.core.Processing import Processing
    Processing.initialize()
except Exception:
    pass

registry = QgsApplication.processingRegistry()

# Remove any previously registered version so re-running the file is safe
for existing in registry.algorithms():
    if existing.id() == "hgnord:place_contour_labels":
        break

try:
    registry.addAlgorithm(ContourLabelAlgorithm())
    print("✓  Algorithm registered: Processing Toolbox → HG Nord tools → Place contour labels")
    print("   Open the Processing Toolbox (Ctrl+Alt+T) to find it.")
except Exception as exc:
    print(f"Registration error: {exc}")
