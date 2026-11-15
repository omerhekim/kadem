# Changelog

## 0.3.0

- The program is now called KADEM (Kinematic–Kinetic Automated Data Extraction in Motion). Projects and templates from
  version 0.2 open unchanged; EMG channel mappings and the language preference are carried over.
- Files page: the tick box now means "included in the computation". Rows are selected for bulk actions by clicking
  (Ctrl / Shift).
- Custom windows and reference instants can be edited. Deleting one that is in use first shows what will be deleted
  with it.
- Window boundaries at a reference instant can be shifted in ms or %GC, as boundaries at events already could.
- New statistics: area of the largest negative lobe; area, extremum and time of the first positive and first negative
  lobe.
- Affected sides can be pasted in bulk from Excel; the patient list can be copied to the clipboard.
- Kinetic completeness: `Kinetic_Complete` column on the patient sheet, an Error entry in the Warnings sheet and a
  notice after the run when a side has no kinetic cycle.
- The Run page warns when EMG amplitude variables are requested without normalization, and asks before overwriting
  existing output files.
- The top bar and side menu adapt to narrow windows.

## 0.2.0

- Measurement date is read from the C3D file or from the folder name.
- English interface and output.
- Excel workbook written with formulas linking trial, patient and long sheets to the cycle sheet; sheet protection;
  algorithm sheet.
