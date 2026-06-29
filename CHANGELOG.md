# Changelog

## [1.3.1] – 2025-06-29

### Fixed
- **Windows fatal crash** (access violation) when running the tool on Shapefile
  layers. Root cause: `getFeatures()` was being called on the contour layer
  while it was already open for editing (`startEditing()`). On Windows, the
  GDAL Shapefile driver locks the `.dbf` file for writing and refuses a
  simultaneous read, causing a fatal access violation. Fix: all contour
  features (geometry + elevation attribute) are now read into a plain Python
  list **before** the edit session opens. The edit session then performs only
  writes, with zero file reads, eliminating the conflict entirely.

## [1.3.0] – 2025-06-25

### Added
- **"Use selected lines only" parameter** in `contour_label_algorithm.py`
  - When ticked, only the lines currently selected in the reference line layer
    are processed
  - Enables an area-by-area workflow: draw all reference lines first, then
    select a subset, tick the option, and run the tool to label one region at
    a time
  - Raises a clear error if the option is ticked but nothing is selected

### Changed
- Reference line processing is now **per-line** instead of first-feature-only:
  all features in the layer (or the current selection) are iterated, each with
  its own elevation detection and orientation check
- Progress bar now reflects progress across all reference lines combined
- Log output shows a per-line summary (placed / skipped) plus a grand total

## [1.2.0] – 2025-06-25

### Added
- `contour_label_algorithm.py` — QGIS Processing Toolbox algorithm
  - Appears under **HG Nord tools → Place contour labels**
  - Integrated help panel, progress bar, cancel support
  - Consistent metadata pattern matching HG Nord `.gen` importer
- README updated with Processing Toolbox usage instructions

## [1.1.0] – 2025-06-25

### Added
- `contour_label_dialog.py` — PyQGIS floating dialog front end

## [1.0.0] – 2025-06-25

### Added
- Initial release of `contour_label_placer.py`
- Automatic intersection, rotation modes, uphill direction modes
- Auto-creation of `lbl_x`, `lbl_y`, `lbl_rot` (Shapefile-safe ≤10 chars)
- MIT licence
