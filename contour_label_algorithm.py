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
    3. In the Processing Toolbox, click the small cogwheel → Scripts →
       "Reload scripts" (or restart QGIS).
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
    QgsGeometry,
    QgsPointXY,
    QgsField,
    QgsWkbTypes,
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
            "Automatically places and rotates contour/isoline labels along a "
            "user-drawn reference line, writing label positions and rotation "
            "angles into three attribute fields on the contour layer.<br><br>"

            "<b>Workflow:</b><br>"
            "1. Draw a reference line crossing the contours you want to label "
            "(Layer → New Temporary Scratch Layer, geometry type: Line). "
            "Draw from the downhill end toward the uphill end when using "
            "'Reference line draw direction'.<br>"
            "2. Run this tool and choose your layers and options below.<br>"
            "3. After the tool finishes, open <i>Layer Properties → Labels → "
            "Placement</i> and connect the Data Defined overrides:<br>"
            "&nbsp;&nbsp;&nbsp;• X Coordinate &nbsp;→&nbsp; <code>lbl_x</code><br>"
            "&nbsp;&nbsp;&nbsp;• Y Coordinate &nbsp;→&nbsp; <code>lbl_y</code><br>"
            "&nbsp;&nbsp;&nbsp;• Rotation &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;→&nbsp; <code>lbl_rot</code><br>"
            "This step is only needed once per layer.<br><br>"

            "<b>Rotation mode:</b><br>"
            "• <i>Contour tangent</i> — each label independently follows the "
            "local direction of its contour. Labels may have slightly different "
            "angles from one another.<br>"
            "• <i>Reference line</i> — all labels share the same angle derived "
            "from the reference line. Gives a cleaner, more uniform look.<br><br>"

            "<b>Label direction:</b><br>"
            "• <i>Low → High (auto)</i> — the tool reads the elevation field "
            "to detect which end of the reference line is uphill and orients "
            "label tops toward higher elevation. <b>Recommended.</b><br>"
            "• <i>High → Low (auto)</i> — same auto-detection; label tops face "
            "toward lower elevation.<br>"
            "• <i>Reference line draw direction</i> — uphill = the direction "
            "you drew the line (first click → last click). No elevation field "
            "needed.<br><br>"

            "<b>Output fields written to the contour layer:</b><br>"
            "<code>lbl_x</code>, <code>lbl_y</code>, <code>lbl_rot</code> "
            "(created automatically if they do not exist). Field names are "
            "≤ 10 characters for Shapefile compatibility.<br><br>"

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
                self.tr("Reference line"),
                types=[QgsProcessing.TypeVectorLine],
            )
        )

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
        elevation_field = self.parameterAsString(     parameters, self.ELEVATION_FIELD,   context) or None
        rotation_idx    = self.parameterAsEnum(       parameters, self.ROTATION_MODE,     context)
        direction_idx   = self.parameterAsEnum(       parameters, self.UPHILL_DIRECTION,  context)

        rotation_mode    = ["contour", "reference"][rotation_idx]
        uphill_direction = ["low_to_high", "high_to_low", "reference"][direction_idx]

        # Validation
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
                "Contour layer and reference line must be different layers.",
                fatalError=True,
            )
            return {}

        # Elevation field check
        fields = contour_layer.fields()
        if elevation_field and fields.indexOf(elevation_field) == -1:
            feedback.reportError(
                f"Elevation field '{elevation_field}' not found in contour layer.",
                fatalError=True,
            )
            return {}
        if elevation_field:
            feedback.pushInfo(f"✓ Elevation field '{elevation_field}' found.")

        # Create label fields if missing
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
            feedback.pushInfo(f"✓ Created fields: {[f.name() for f in fields_to_create]}")
        else:
            feedback.pushInfo(f"✓ Fields {FIELD_X}, {FIELD_Y}, {FIELD_ROT} already exist — reusing.")

        fields   = contour_layer.fields()
        idx_x    = fields.indexOf(FIELD_X)
        idx_y    = fields.indexOf(FIELD_Y)
        idx_rot  = fields.indexOf(FIELD_ROT)
        idx_elev = fields.indexOf(elevation_field) if elevation_field else None

        # Read reference line
        ref_features = list(ref_layer.getFeatures())
        if not ref_features:
            feedback.reportError("Reference line layer has no features.", fatalError=True)
            return {}

        ref_geom = ref_features[0].geometry()
        ref_line = (ref_geom.asPolyline()
                    if not ref_geom.isMultipart()
                    else ref_geom.asMultiPolyline()[0])

        slope_start = QgsPointXY(ref_line[0])
        slope_end   = QgsPointXY(ref_line[-1])
        ref_dx = slope_end.x() - slope_start.x()
        ref_dy = slope_end.y() - slope_start.y()
        ref_label_rotation = (-math.degrees(math.atan2(ref_dy, ref_dx)) + 90) % 360

        # Elevation-based direction detection
        elev_at_start = None
        elev_at_end   = None
        elev_flip     = False

        if uphill_direction in ("low_to_high", "high_to_low") and idx_elev is not None:
            start_geom     = QgsGeometry.fromPointXY(slope_start)
            end_geom       = QgsGeometry.fromPointXY(slope_end)
            min_dist_start = float('inf')
            min_dist_end   = float('inf')

            for feat in contour_layer.getFeatures():
                if feedback.isCanceled():
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
                    "Could not sample elevation at reference line endpoints. "
                    "Falling back to reference line draw direction."
                )
                uphill_direction = "reference"
            else:
                feedback.pushInfo(f"  Elevation at START : {elev_at_start}")
                feedback.pushInfo(f"  Elevation at END   : {elev_at_end}")
                elev_flip = (elev_at_end < elev_at_start) if uphill_direction == "low_to_high" \
                            else (elev_at_end > elev_at_start)
                feedback.pushInfo(f"  Direction flip applied: {elev_flip}")

        # Main loop
        total         = contour_layer.featureCount()
        placed_count  = 0
        skipped_count = 0

        contour_layer.startEditing()

        for i, contour_feat in enumerate(contour_layer.getFeatures()):
            if feedback.isCanceled():
                contour_layer.rollBack()
                return {}

            feedback.setProgress(int(i / total * 100))
            contour_geom = contour_feat.geometry()
            intersection = contour_geom.intersection(ref_geom)

            if intersection.isEmpty():
                skipped_count += 1
                continue

            pt = (intersection.asMultiPoint()[0]
                  if intersection.isMultipart()
                  else intersection.asPoint())
            if pt is None:
                skipped_count += 1
                continue

            label_pos = QgsPointXY(pt)

            # Uphill vector
            if uphill_direction == "reference" or (not elev_flip):
                to_uphill_x = slope_end.x() - label_pos.x()
                to_uphill_y = slope_end.y() - label_pos.y()
            else:
                to_uphill_x = slope_start.x() - label_pos.x()
                to_uphill_y = slope_start.y() - label_pos.y()

            # Override for pure "reference" mode
            if uphill_direction == "reference":
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

            contour_layer.changeAttributeValue(contour_feat.id(), idx_x,   label_pos.x())
            contour_layer.changeAttributeValue(contour_feat.id(), idx_y,   label_pos.y())
            contour_layer.changeAttributeValue(contour_feat.id(), idx_rot, label_rotation)
            placed_count += 1

        contour_layer.commitChanges()
        contour_layer.triggerRepaint()
        feedback.setProgress(100)

        feedback.pushInfo("")
        feedback.pushInfo("=" * 50)
        feedback.pushInfo(f"  Labels placed : {placed_count}")
        feedback.pushInfo(f"  Skipped       : {skipped_count}  (no intersection)")
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

# Remove any old version so re-running the file is safe
for existing in registry.algorithms():
    if existing.id() == "hgnord:place_contour_labels":
        registry.providerById("hgnord") and None   # keep provider
        break

try:
    registry.addAlgorithm(ContourLabelAlgorithm())
    print("✓  Algorithm registered: Processing Toolbox → HG Nord tools → Place contour labels")
    print("   Open the Processing Toolbox (Ctrl+Alt+T) to find it.")
except Exception as exc:
    print(f"Registration error: {exc}")
