# Changelog

## [1.2.0] – 2025-06-25

### Added
- `contour_label_algorithm.py` — QGIS Processing Toolbox algorithm
  - Appears under **HG Nord tools → Place contour labels** alongside other HG Nord tools
  - Integrated help panel with full parameter descriptions
  - Progress bar and cancel support via `feedback.isCanceled()`
  - Consistent metadata structure (`name`, `displayName`, `group`, `groupId`, `shortHelpString`)
    matching the HG Nord `.gen` importer pattern
  - Can be loaded temporarily (Python Console) or permanently (user scripts folder)
- README updated with Processing Toolbox usage instructions and comparison table

## [1.1.0] – 2025-06-25

### Added
- `contour_label_dialog.py` — PyQGIS floating dialog front end
- README updated with dialog usage instructions

## [1.0.0] – 2025-06-25

### Added
- Initial release of `contour_label_placer.py`
- Automatic intersection of contour features with a user-drawn reference line
- Two rotation modes: `"contour"` and `"reference"`
- Three uphill direction modes: `"reference"`, `"low_to_high"`, `"high_to_low"`
- Elevation-based slope direction auto-detection
- Dot-product flip check to ensure labels read uphill
- Auto-creation of output fields `lbl_x`, `lbl_y`, `lbl_rot` (Shapefile-safe ≤10 chars)
- MIT licence
