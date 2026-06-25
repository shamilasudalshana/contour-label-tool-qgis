# Changelog

## [1.1.0] – 2025-06-25

### Added
- `contour_label_dialog.py` — PyQGIS dialog front end with dropdowns for all
  options, a live output log, and an inline reminder of the data-defined
  override setup step
- README updated with dialog usage instructions and comparison table

## [1.0.0] – 2025-06-25

### Added
- Initial release of `contour_label_placer.py`
- Automatic intersection of contour features with a user-drawn reference line
- Two rotation modes: `"contour"` and `"reference"`
- Three uphill direction modes: `"reference"`, `"low_to_high"`, `"high_to_low"`
- Elevation-based slope direction auto-detection
- Dot-product flip check to ensure labels read uphill
- Auto-creation of output fields `lbl_x`, `lbl_y`, `lbl_rot` (Shapefile-safe)
- MIT licence
