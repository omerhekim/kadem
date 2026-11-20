# KADEM

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.24401203.svg)](https://doi.org/10.5281/zenodo.24401203)

**Kinematic–Kinetic Automated Data Extraction in Motion** (Türkçe: [BENIOKU.md](BENIOKU.md))

KADEM is a desktop program that extracts event-based gait variables from C3D files processed with Plug-in Gait and writes
them to a single Excel workbook that is ready for SPSS and R. You choose a window, a variable and a statistic from
drop-down lists; the program computes the value in every gait cycle of every trial and aggregates cycles into trial and
patient means.

*Kadem* is an old Turkish word for "step".

> **Research use only.** KADEM is not a medical device. It must not be used on its own for diagnosis or treatment
> decisions.

## What it does

- **Reads C3D files directly.** No Vicon software is needed to run it. It uses the model outputs and events already
  stored in the file.
- **Event-based windows.** Whole cycle, stance, swing, double and single support, any %GC / %stance / %swing range, and
  windows shifted in ms or %GC relative to an event or to a reference instant (for example "10% of the cycle after the
  H2 power peak").
- **Reference instants.** Define an instant such as "peak ankle power", then read any other variable at that instant or
  use it as a window boundary. Peak times of the Winter power phases (A1–A2, K1–K4, H1–H3) are built in.
- **Variables.** Plug-in Gait angles, moments, powers and joint forces; ground reaction force; spatiotemporal
  parameters; toe clearance; EMG (amplitude, activation timing, median frequency, co-contraction).
- **Statistics.** Mean, maximum, minimum, range, timing of peaks, areas (work, impulse), positive and negative lobes,
  slopes, value at an instant, and others.
- **Waveforms** (optional). Time-normalized curves per cycle and per patient, in a separate workbook, as input for SPM
  or plotting.
- **Traceable output.** Besides the patient-level (wide) and long tables the workbook holds every cycle value, a
  variable dictionary, a methods sheet, and an algorithm sheet that states, for every column, how it was computed.
- **Turkish and English** interface, warnings and output.

## What it deliberately does not do

- **It does not correct data.** Events are not moved, gaps are not filled, outliers are not removed. Every suspicious
  condition is written to the Warnings sheet instead. Corrections belong in the processing software.
- **It does not detect events.** It uses the Foot Strike and Foot Off events in the C3D file.
- **It does not compute joint kinematics or kinetics.** It reads the model outputs that are in the file.

## Scope and limitations

- Written for and tested with C3D files exported from Vicon Nexus after Plug-in Gait lower-body processing. The
  lower-body outputs of the Conventional Gait Model 2.2 (pyCGM2) have also been tested by the author and work. Other
  models that write the same output names are expected to work but have not been tested. Upper-body outputs have not
  been tested, and outputs with other names (for example Oxford Foot Model segments) cannot be selected yet.
- Kinetic variables are computed only in cycles with force-plate contact on that side, judged from that side's ground
  reaction force in the file.
- Toe clearance is measured from the TOE marker relative to a floor plane fitted to mid-stance TOE positions in the
  same trial, not relative to a static trial.

## Installation

KADEM runs on Windows 10 or 11. It shows its interface in an application window of Microsoft Edge (or Chrome) and
talks only to a local server on `127.0.0.1`. No data leaves the computer.

### Download (no Python needed)

1. Open the [Releases](https://github.com/omerhekim/kadem/releases) page and download `KADEM_Windows.zip` from the latest version.
2. Extract it to any folder and run `KADEM.exe`. Keep the `_internal` folder next to it.
3. The program is not code-signed, so Windows SmartScreen may warn on the first start: choose "More info → Run anyway".

### Run from source (for developers)

Requires Python 3.10 or newer.

```
pip install -r requirements.txt
python -m kadem
```

On Windows, `calistir.bat` does the same. `build_exe.bat` builds `dist\KADEM\KADEM.exe` locally; the release builds
are made the same way on GitHub Actions (`.github/workflows/build.yml`).

## Quick start

1. **Files.** Add a folder; all C3D files in its subfolders are listed. The patient name is taken from the file name
   and the measurement date from the folder name (for example `...\Patient Name\13 01 2026\`). A ticked file is
   included in the computation.
2. **EMG channels.** Map each EMG channel to a muscle and side. The mapping is remembered.
3. **Queries.** Pick a window or instant, a variable and a statistic, then "Add to list". Each query becomes a column.
   Query lists can be saved as templates and shared.
4. **Patients and MVIC.** Optionally enter the affected side (adds affected / unaffected / difference / LSI columns)
   and MVIC values. Sides can be pasted in bulk from Excel.
5. **Settings.** EMG filter chain and normalization, missing-data rule, averaging method.
6. **Run.** Choose the output folder and file name.

## The Excel workbook

| Sheet | Content |
|---|---|
| 1_Patient_Level | One row per patient + date; side-specific variables as `L_` and `R_` columns |
| 2_Long_Format | Patient, side, variable, mean, SD, N, CV |
| 3_Trial_Means | Means per trial |
| 4_All_Cycles | The value of every cycle. The only editable sheet |
| 5_Warnings | Everything the program found suspicious |
| 6_Outliers | Outliers, listed but not removed |
| 8_Variable_Dictionary | Definition of every column |
| 9_Methods | Settings and methods text |
| 12_Algorithm | Step-by-step computation of every column |

The trial, patient and long sheets are linked to the cycle sheet by formulas. If you change a cycle value or set
`Excluded` to 1 on the cycle sheet, the means update. The other sheets are protected without a password against
accidental edits.

## Validation

The values were compared with exports from Vicon Polygon and with Noraxon myoRESEARCH on the developer's clinical
data.

## Citing

KADEM is archived on Zenodo. If you use it in a publication, please cite the version you used:

> Hekim Ö. *KADEM: Kinematic–Kinetic Automated Data Extraction in Motion* (Version 0.3.1) [Computer software].
> Zenodo; 2026. https://doi.org/10.5281/zenodo.24401204

The DOI [10.5281/zenodo.24401203](https://doi.org/10.5281/zenodo.24401203) refers to all versions and always resolves to the latest one; the DOI of each
version is listed on that Zenodo page. Citation metadata: [CITATION.cff](CITATION.cff).

## Use of AI in development

Most of the source code was written with an AI coding assistant (Claude, Anthropic) under the direction of the author,
who specified the methods, reviewed the behaviour and validated the results against independent software.

## Trademarks

Vicon, Nexus, Polygon and Plug-in Gait are trademarks of Vicon Motion Systems Ltd. Noraxon and myoRESEARCH are
trademarks of Noraxon USA Inc. KADEM is an independent project. It is not affiliated with or endorsed by these
companies and contains none of their software.

## License

See [LICENSE](LICENSE).
