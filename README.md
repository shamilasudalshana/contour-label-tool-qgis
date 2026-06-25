# Contour Label Placer — QGIS Tool

Automates the placement and rotation of contour/isoline labels in QGIS along a user-drawn reference line. Eliminates the slow manual workflow of using the QGIS Label Toolbar ("Move a Label" / "Rotate a Label") one feature at a time.

Two ways to use it — choose what suits you:

| | `contour_label_dialog.py` | `contour_label_placer.py` |
|---|---|---|
| **Best for** | Colleagues unfamiliar with scripts | Power users / automation |
| **Interface** | Click-through dialog window | Edit parameters directly in code |
| **Requires** | QGIS Python Console (one paste) | QGIS Python Console |

---

## Features

- Places labels at the intersection of contours with a reference line you draw
- Two **rotation modes**: follow each contour's own tangent, or use a uniform angle
- Three **uphill direction options**: draw-direction, auto-detect from elevation (low→high or high→low)
- Works with **Shapefiles and GeoPackages** (field names ≤ 10 characters)
- Auto-creates the three required label attribute fields
- Dialog front end with layer/field dropdowns and a live output log

---

## Requirements

| Requirement | Notes |
|---|---|
| QGIS 3.x | Any recent release |
| Python / PyQGIS | Bundled with QGIS — nothing extra to install |

---

## Files

```
contour-label-tool/
├── contour_label_dialog.py   ← dialog UI (recommended for most users)
├── contour_label_placer.py   ← script-only version
├── README.md
├── LICENSE                   ← MIT
├── CHANGELOG.md
└── .gitignore
```

---

## Usage — Dialog version (recommended)

### Step 1 — Draw a reference line

1. In QGIS, go to **Layer → Create Layer → New Temporary Scratch Layer**
2. Set geometry type to **Line** and click OK
3. Toggle editing on the scratch layer, then press **L** (Add Line Feature)
4. Click your **first point at the foot of the slope** (downhill end)
5. Click one or more points moving uphill, then **right-click to finish**
6. Save the scratch layer edits

> **Tip:** One reference line can cross many contours at once. If you use the "Low → High" or "High → Low" direction modes, the direction you draw does not matter — the tool detects it automatically from the elevation field.

---

### Step 2 — Open the dialog

1. Open the **QGIS Python Console**
   - Menu: `Plugins → Python Console`
   - Or press `Ctrl + Alt + P`
2. Click the **Show Editor** button (pencil icon in the console toolbar)
3. Click **Open File** (folder icon) and select `contour_label_dialog.py`
   — or paste the entire file contents into the editor
4. Press **Run** (green play button ▶)

The dialog window opens immediately.

---

### Step 3 — Fill in the dialog

| Field | What to choose |
|---|---|
| **Contour layer** | Your isoline/contour polyline layer |
| **Reference line** | The scratch layer you drew in Step 1 |
| **Elevation field** | The numeric attribute holding elevation values (e.g. `ELEV`) |
| **Rotation mode** | See options below |
| **Label direction** | See options below |

Click **▶ Place Labels**.

---

### Step 4 — Connect fields to QGIS label data-defined overrides ⚠️

This step is required **once per layer** to tell QGIS to use the computed positions.

1. Right-click your contour layer → **Properties → Labels**
2. Enable labeling — choose your elevation field as the label text (e.g. `ELEV`)
3. Go to the **Placement** tab
4. Find the three **Data Defined** icons (small yellow buttons next to coordinate/rotation fields):
   - Next to **X Coordinate** → click the icon → **Field type** → select `lbl_x`
   - Next to **Y Coordinate** → select **`lbl_y`**
   - Next to **Rotation** → select **`lbl_rot`**
5. Click **OK**

Labels will now appear at the positions and angles the tool calculated.

> After re-running the tool (e.g. with a new reference line), just refresh the map — the data-defined links stay in place and pick up the new values automatically. You only need to do Step 4 once per layer.

---

## Usage — Script version

If you prefer to work directly in the Python Console editor:

1. Open `contour_label_placer.py`
2. Edit the parameters at the bottom:

```python
autoplace_contour_labels(
    contour_layer_name        = "your_contour_layer",   # name in QGIS Layers panel
    reference_line_layer_name = "New scratch layer",    # name of your reference line
    elevation_field           = "ELEV",                 # attribute field with elevation
    rotation_mode             = "contour",              # "contour" or "reference"
    uphill_direction          = "low_to_high"           # see options below
)
```

3. Press **Run**

The script prints a step-by-step log and reminds you of the data-defined override setup.

---

## Options

### Rotation mode

| Value | Behaviour |
|---|---|
| `"contour"` — *Follow contour tangent* | Each label rotates individually to follow its own contour tangent at the intersection point. Labels may have slightly different angles — natural look. |
| `"reference"` — *Follow reference line* | All labels along the transect share the same angle (the direction of the reference line). Cleaner, more uniform look. |

### Label direction

| Value | Behaviour |
|---|---|
| `"low_to_high"` — *Auto: Low → High* | Script detects slope from the elevation field — label tops face toward higher elevation. **Recommended.** |
| `"high_to_low"` — *Auto: High → Low* | Same auto-detection but label tops face toward lower elevation. |
| `"reference"` — *Manual: draw direction* | Uphill = the direction you drew the reference line (first click → last click). No elevation field needed. |

---

## Output fields

The tool writes three fields to your contour layer:

| Field | Type | Used for |
|---|---|---|
| `lbl_x` | Double | Label X coordinate — connect to Data Defined X in QGIS |
| `lbl_y` | Double | Label Y coordinate — connect to Data Defined Y in QGIS |
| `lbl_rot` | Double | Label rotation in degrees — connect to Data Defined Rotation |

Field names are ≤ 10 characters for Shapefile compatibility.

> **GeoPackage users:** you can change the field names to longer strings by editing the `FIELD_X`, `FIELD_Y`, `FIELD_ROT` constants at the top of either script.

---

## How it works

```
Reference line drawn by user
         │
         │  ← drawn across all contours to be labelled
         │
         ↓
For each contour feature:
  1. Compute intersection point   → label position (lbl_x, lbl_y)
  2. Find nearest contour segment at intersection
  3. Compute tangent angle        → rotation candidate
  4. Dot-product flip check       → ensure label reads uphill
  5. Write lbl_x, lbl_y, lbl_rot to the attribute table
```

---

## Tips

- **Multiple transects**: add more than one line to your scratch layer before running. All crossings are processed in one go.
- **Fine-tuning**: after the tool runs, you can still adjust individual labels manually using the QGIS Label Toolbar. The computed values are the starting point, not a lock.
- **Re-running**: running the tool again overwrites `lbl_x`, `lbl_y`, `lbl_rot` only for features that intersect the new reference line.

---

## Project background

Developed at **HG Nord — Hydro-Geologie-Nord PartGmbB** (Mecklenburg-Vorpommern, Germany) to streamline cartographic label placement on groundwater depth contour maps. The tool replaces a fully manual workflow with a single dialog interaction while preserving fine-grained control via the standard QGIS label data-defined override system.

---

## Licence

MIT — see [LICENSE](LICENSE)
