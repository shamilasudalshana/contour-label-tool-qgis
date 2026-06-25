"""
contour_label_placer.py
=======================
Automatically places and rotates contour/isoline labels along a
user-drawn reference line.

Field names are kept to ≤10 characters so the script works with
Shapefiles as well as GeoPackage layers:
    lbl_x    → label X coordinate   (data-defined override: X Coordinate)
    lbl_y    → label Y coordinate   (data-defined override: Y Coordinate)
    lbl_rot  → label rotation angle (data-defined override: Rotation)

After running, connect these fields to the QGIS label data-defined
overrides:
    Layer Properties → Labels → Placement → Data Defined:
        X Coordinate → lbl_x
        Y Coordinate → lbl_y
        Rotation     → lbl_rot

Author : HG Nord – Hydro-Geologie-Nord PartGmbB
License: MIT
"""

from qgis.core import (
    QgsProject, QgsGeometry, QgsPointXY,
    QgsField, QgsVectorLayer
)
from PyQt5.QtCore import QVariant
import math


# ---------------------------------------------------------------------------
# Field name constants  (≤10 chars — Shapefile safe)
# ---------------------------------------------------------------------------
FIELD_X   = "lbl_x"
FIELD_Y   = "lbl_y"
FIELD_ROT = "lbl_rot"


def autoplace_contour_labels(
    contour_layer_name: str,
    reference_line_layer_name: str,
    elevation_field: str = None,
    rotation_mode: str = "contour",
    uphill_direction: str = "reference"
):
    """
    Place and rotate contour labels along a reference line.

    Parameters
    ----------
    contour_layer_name : str
        Name of the contour/isoline polyline layer in the QGIS project.
    reference_line_layer_name : str
        Name of the reference line layer (usually a temporary scratch layer).
        Draw this line crossing all contours you want to label.
        Start point = downhill end, end point = uphill end
        (only matters when uphill_direction = "reference").
    elevation_field : str, optional
        Attribute field holding contour elevation values.
        Required when uphill_direction is "low_to_high" or "high_to_low".
    rotation_mode : str
        "contour"   – each label rotates to follow its own contour tangent.
        "reference" – all labels share the reference line angle (cleaner look).
    uphill_direction : str
        "reference"   – uphill = the direction the reference line was drawn.
        "low_to_high" – label top faces toward higher elevation automatically.
        "high_to_low" – label top faces toward lower elevation.
    """

    # ------------------------------------------------------------------
    # 1. Parameter validation
    # ------------------------------------------------------------------
    if rotation_mode not in ("contour", "reference"):
        print("ERROR: rotation_mode must be 'contour' or 'reference'")
        return

    if uphill_direction not in ("reference", "low_to_high", "high_to_low"):
        print("ERROR: uphill_direction must be 'reference', 'low_to_high', or 'high_to_low'")
        return

    if uphill_direction in ("low_to_high", "high_to_low") and not elevation_field:
        print("ERROR: elevation_field is required when uphill_direction is "
              "'low_to_high' or 'high_to_low'")
        return

    # ------------------------------------------------------------------
    # 2. Fetch layers
    # ------------------------------------------------------------------
    project = QgsProject.instance()

    contour_layers = project.mapLayersByName(contour_layer_name)
    ref_layers     = project.mapLayersByName(reference_line_layer_name)

    if not contour_layers:
        print(f"ERROR: Layer '{contour_layer_name}' not found.")
        return
    if not ref_layers:
        print(f"ERROR: Layer '{reference_line_layer_name}' not found.")
        return

    contour_layer = contour_layers[0]
    ref_layer     = ref_layers[0]

    # ------------------------------------------------------------------
    # 3. Validate elevation field
    # ------------------------------------------------------------------
    fields = contour_layer.fields()
    if elevation_field:
        if fields.indexOf(elevation_field) == -1:
            available = [f.name() for f in fields]
            print(f"ERROR: Elevation field '{elevation_field}' not found.")
            print(f"  Available fields: {available}")
            return
        else:
            print(f"✓ Elevation field '{elevation_field}' found.")

    # ------------------------------------------------------------------
    # 4. Create label fields if they don't already exist
    # ------------------------------------------------------------------
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
        created_names = [f.name() for f in fields_to_create]
        print(f"✓ Created fields: {created_names}")
    else:
        print(f"✓ Fields {FIELD_X}, {FIELD_Y}, {FIELD_ROT} already exist — reusing.")

    # Refresh indices after possible field creation
    fields   = contour_layer.fields()
    idx_x    = fields.indexOf(FIELD_X)
    idx_y    = fields.indexOf(FIELD_Y)
    idx_rot  = fields.indexOf(FIELD_ROT)
    idx_elev = fields.indexOf(elevation_field) if elevation_field else None

    # ------------------------------------------------------------------
    # 5. Read reference line
    # ------------------------------------------------------------------
    ref_features = list(ref_layer.getFeatures())
    if not ref_features:
        print("ERROR: Reference line layer has no features.")
        return

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

    # ------------------------------------------------------------------
    # 6. Elevation-based direction detection
    # ------------------------------------------------------------------
    elev_at_start = None
    elev_at_end   = None
    elev_flip     = False   # default

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
            print("WARNING: Could not sample elevation at reference line endpoints. "
                  "Falling back to 'reference' direction.")
            uphill_direction = "reference"
        else:
            print(f"  Elevation at reference line START : {elev_at_start}")
            print(f"  Elevation at reference line END   : {elev_at_end}")

            if uphill_direction == "low_to_high":
                elev_flip = elev_at_end < elev_at_start   # flip if start is higher
            else:  # high_to_low
                elev_flip = elev_at_end > elev_at_start   # flip if start is lower

            print(f"  Direction flip applied: {elev_flip}")

    # ------------------------------------------------------------------
    # 7. Main loop — intersect and write label positions
    # ------------------------------------------------------------------
    contour_layer.startEditing()
    placed_count  = 0
    skipped_count = 0

    for contour_feat in contour_layer.getFeatures():
        contour_geom = contour_feat.geometry()
        intersection = contour_geom.intersection(ref_geom)

        if intersection.isEmpty():
            skipped_count += 1
            continue

        # Resolve intersection point
        if intersection.isMultipart():
            pts = intersection.asMultiPoint()
            pt  = pts[0] if pts else None
        else:
            pt = intersection.asPoint()

        if pt is None:
            skipped_count += 1
            continue

        label_pos = QgsPointXY(pt)

        # ── Uphill vector for orientation check ──────────────────────
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

        # ── Rotation ─────────────────────────────────────────────────
        if rotation_mode == "contour":
            # Find nearest segment on the contour
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

            # Flip check: label "up" = perpendicular-left of contour dir
            label_up_x = -dy
            label_up_y =  dx
            dot = label_up_x * to_uphill_x + label_up_y * to_uphill_y
            if dot < 0:
                label_rotation = (label_rotation + 180) % 360

        else:  # rotation_mode == "reference"
            label_rotation = ref_label_rotation
            label_up_x = ref_dx
            label_up_y = ref_dy
            dot = label_up_x * to_uphill_x + label_up_y * to_uphill_y
            if dot < 0:
                label_rotation = (label_rotation + 180) % 360

        # ── Write values ─────────────────────────────────────────────
        contour_layer.changeAttributeValue(contour_feat.id(), idx_x,   label_pos.x())
        contour_layer.changeAttributeValue(contour_feat.id(), idx_y,   label_pos.y())
        contour_layer.changeAttributeValue(contour_feat.id(), idx_rot, label_rotation)
        placed_count += 1

    contour_layer.commitChanges()
    contour_layer.triggerRepaint()

    # ------------------------------------------------------------------
    # 8. Summary
    # ------------------------------------------------------------------
    print(f"\n{'='*50}")
    print(f"  Done  (rotation='{rotation_mode}', direction='{uphill_direction}')")
    print(f"  Labels placed : {placed_count}")
    print(f"  Skipped       : {skipped_count}  (no intersection with reference line)")
    print(f"{'='*50}")
    print(f"\nNEXT STEP — connect fields to QGIS label data-defined overrides:")
    print(f"  Layer Properties → Labels → Placement → Data Defined:")
    print(f"    X Coordinate → {FIELD_X}")
    print(f"    Y Coordinate → {FIELD_Y}")
    print(f"    Rotation     → {FIELD_ROT}")


# ---------------------------------------------------------------------------
# RUN — edit these four parameters to match your project
# ---------------------------------------------------------------------------
if __name__ == "__console__" or True:
    autoplace_contour_labels(
        contour_layer_name        = "GWD_KAL_01_WG_Warin_test",  # your contour layer name
        reference_line_layer_name = "New_scratch_line_1",         # your reference line name
        elevation_field           = "ELEV",                        # elevation attribute field
        rotation_mode             = "contour",    # "contour" or "reference"
        uphill_direction          = "low_to_high" # "reference", "low_to_high", "high_to_low"
    )
