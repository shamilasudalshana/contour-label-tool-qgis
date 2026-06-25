# Contour Label Placer — QGIS Tool

Automates the placement and rotation of contour/isoline labels in QGIS along a user-drawn reference line. Eliminates the slow manual workflow of using the QGIS Label Toolbar ("Move a Label" / "Rotate a Label") one feature at a time.

Three ways to use it — choose what suits you:

| | `contour_label_algorithm.py` | `contour_label_dialog.py` | `contour_label_placer.py` |
|---|---|---|---|
| **Best for** | All colleagues — integrates into QGIS like a native tool | Colleagues who prefer a separate window | Power users / scripting |
| **Interface** | Processing Toolbox → HG Nord tools | Floating dialog window | Edit parameters in code |
| **Consistent with** | Other HG Nord Processing tools (e.g. `.gen` importer) | — | — |

---

## Features

- Places labels at the intersection of contours with a reference line you draw
- Two **rotation modes**: follow each contour's own tangent, or use a uniform angle
- Three **uphill direction options**: draw-direction, auto-detect from elevation (low→high or high→low)
- Works with **Shapefiles and GeoPackages** (field names ≤ 10 characters)
- Auto-creates the three required label attribute fields
- Progress bar and cancellation support (Processing Toolbox version)
- Integrated help panel in QGIS (Processing Toolbox version)

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
├── contour_label_algorithm.py  ← Processing Toolbox version (recommended)
├── contour_label_dialog.py     ← floating dialog version
├── contour_label_placer.py     ← script-only version
├── README.md
├── LICENSE                     ← MIT
├── CHANGELOG.md
└── .gitignore
```

---

## Usage — Processing Toolbox version (recommended)

This version integrates into QGIS under **Processing Toolbox → HG Nord tools** alongside other HG Nord tools such as the `.gen` importer. It includes a help panel, progress bar, and cancel button.

### Loading the algorithm

**Option A — Current session only:**

1. Open the **QGIS Python Console** (`Plugins → Python Console` or `Ctrl+Alt+P`)
2. Click **Show Editor** (pencil icon), open `contour_label_algorithm.py`, press **▶ Run**
3. The console prints: `✓ Algorithm registered: Processing Toolbox → HG Nord tools → Place contour labels`
4. Open the **Processing Toolbox** (`Ctrl+Alt+T`) → find it under **HG Nord tools**

**Option B — Permanent (survives QGIS restart):**

1. Go to `Settings → User Profiles → Open Active Profile Folder`
2. Navigate to `processing → scripts`
3. Copy `contour_label_algorithm.py` into that folder
4. In the Processing Toolbox, click **⚙ → Scripts → Reload scripts** (or restart QGIS)
5. The tool will always appear under **Scripts → HG Nord tools**

---

### Step 1 — Draw a reference line

1. Go to **Layer → Create Layer → New Temporary Scratch Layer**
2. Set geometry type to **Line** and click OK
3. Toggle editing on the scratch layer, then press **L** (Add Line Feature)
4. Click your **first point at the foot of the slope** (downhill end)
5. Click one or more points moving uphill, then **right-click to finish**
6. Save the scratch layer edits

> **Tip:** With "Low → High" or "High → Low" direction modes the draw direction does not matter — the tool detects slope automatically from the elevation field.

---

### Step 2 — Run the tool

1. Open the Processing Toolbox (`Ctrl+Alt+T`)
2. Navigate to **HG Nord tools → Place contour labels**
   (or search "contour labels" in the search box at the top)
3. Double-click to open the tool dialog

| Parameter | What to choose |
|---|---|
| **Contour layer** | Your isoline/contour polyline layer |
| **Reference line** | The scratch layer you drew in Step 1 |
| **Elevation field** | Numeric attribute holding elevation values (e.g. `ELEV`) |
| **Rotation mode** | See options below |
| **Label direction** | See options below |

Click **Run**. A progress bar shows processing status; click **Cancel** to abort.

The **Help** panel on the right of the tool dialog contains full parameter descriptions.

---

### Step 3 — Connect fields to QGIS label data-defined overrides ⚠️

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

> After re-running the tool (e.g. with a new reference line), just refresh the map — the data-defined links stay in place and pick up the new values automatically. You only need to do Step 3 once per layer.

---

## Usage — Dialog version

For colleagues who prefer a floating window rather than the Processing Toolbox:

1. Open the **QGIS Python Console** (`Ctrl+Alt+P`)
2. Click **Show Editor**, open `contour_label_dialog.py`, press **▶ Run**
3. A dialog window opens with dropdowns for all options and a live output log

Follow Steps 1 and 3 from the Processing Toolbox instructions above (draw reference line, then connect data-defined overrides).

---

## Usage — Script version

For power users or batch workflows:

1. Open `contour_label_placer.py` in the QGIS Python Console editor
2. Edit the parameters at the bottom:

```python
autoplace_contour_labels(
    contour_layer_name        = "your_contour_layer",
    reference_line_layer_name = "New scratch layer",
    elevation_field           = "ELEV",
    rotation_mode             = "contour",      # "contour" or "reference"
    uphill_direction          = "low_to_high"   # see options below
)
```

3. Press **▶ Run**

---

## Options

### Rotation mode

| Value | Behaviour |
|---|---|
| `"contour"` — *Contour tangent* | Each label rotates individually to follow its own contour tangent at the intersection point. Natural look, labels may differ slightly in angle. |
| `"reference"` — *Reference line* | All labels share the same angle derived from the reference line. Cleaner, more uniform look. |

### Label direction

| Value | Behaviour |
|---|---|
| `"low_to_high"` — *Low → High (auto)* | Script reads the elevation field to detect which end of the reference line is uphill. Label tops face toward higher elevation. **Recommended.** |
| `"high_to_low"` — *High → Low (auto)* | Same auto-detection; label tops face toward lower elevation. |
| `"reference"` — *Draw direction (manual)* | Uphill = the direction you drew the reference line (first click → last click). No elevation field needed. |

---

## Output fields

The tool writes three fields to your contour layer:

| Field | Type | Used for |
|---|---|---|
| `lbl_x` | Double | Label X coordinate — connect to Data Defined X in QGIS |
| `lbl_y` | Double | Label Y coordinate — connect to Data Defined Y in QGIS |
| `lbl_rot` | Double | Label rotation in degrees — connect to Data Defined Rotation |

Field names are ≤ 10 characters for Shapefile compatibility.

> **GeoPackage users:** you can change field names to longer strings by editing `FIELD_X`, `FIELD_Y`, `FIELD_ROT` at the top of any of the three scripts.

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

- **Multiple transects**: add more lines to your scratch layer before running. All crossings are processed in one go.
- **Fine-tuning**: after the tool runs you can still adjust individual labels manually with the QGIS Label Toolbar. The computed values are the starting point, not a lock.
- **Re-running**: running the tool again overwrites `lbl_x`, `lbl_y`, `lbl_rot` only for features that intersect the current reference line.

---

## Project background

Developed at **HG Nord — Hydro-Geologie-Nord PartGmbB** (Mecklenburg-Vorpommern, Germany) to streamline cartographic label placement on groundwater depth contour maps. Part of a growing suite of in-house QGIS Processing tools for hydrogeological workflows.

---

## Licence

MIT — see [LICENSE](LICENSE)
