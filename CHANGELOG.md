# Changelog

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
