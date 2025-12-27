# Earthquake Arrival Time Simulation
Interactive earthquake arrival-time simulator plus Scratch assets for recreating the original project.

## Overview
This workspace hosts a Python/Pygame rewrite of the Scratch project "地震の到達時間シミュレーション" together with the original `.sb3` assets and supporting geographic datasets. The Python application renders Japans map, lets users place an epicenter, and visualizes P- and S-wave travel, arrival times, and estimated Japan Meteorological Agency (JMA) intensities.

The `sb3_v2` directory contains the fully extracted Scratch project so that the visual scripts and media can be reviewed while reproducing the experience feature-by-feature. A bundled GeoJSON dataset (`JMA_Region-main/震央地名.geojson`) supplies polygon boundaries and multilingual region names that drive both the locator logic and the rendered map.

## Technology Stack
- Language/Runtime: Python 3.9+ (CPython)
- Framework(s): Pygame for visualization/input handling
- Key Dependencies: `pygame`, `numpy`, GeoJSON dataset from JMA_Region-main
- Build Tools: `pip` / `venv` (no Node/npm assets present)

## Project Structure
```
.
├─earthquake_sim/              # Python rewrite of the simulator
│ ├─config.py                  # Global constants (wave speeds, colors, window size, map bounds)
│ ├─earthquake.py              # Earthquake domain model & wave arrival math
│ ├─epicenter.py               # GeoJSON-based epicenter region lookup utilities
│ ├─intensity.py               # JMA intensity calculations & color scale helpers
│ ├─map_renderer.py            # GeoJSON polygon loading and Pygame drawing
│ ├─main.py                    # EarthquakeSimulator UI loop, event handling, rendering
│ └─requirements.txt           # Python dependency list (pygame, numpy)
├─sb3_v2/                      # Extracted Scratch v2 project assets (wav/svg/png/project.json)
├─JMA_Region-main/             # Upstream GIS dataset (README, LICENSE, 震央地名.geojson)
├─JMA_Region-main.zip          # Zip archive of the same dataset for reference
├─地震の到達時間シミュレーション v2.sb3 # Scratch project v2 package
├─地震シミュレーション ver3.2.sb3      # Additional Scratch project reference
├─.snow / .claude              # Tooling metadata for Codex/Snow environments
└─AGENTS.md                    # (This document) project overview
```

## Key Features
- Interactive placement of epicenters with keyboard/mouse controls and on-screen guidance.
- Real-time visualization of expanding P- and S-wave fronts scaled to kilometers over Japans map.
- Built-in JMA intensity estimation (formulas + color-coded scale) for quick impact assessment.
- GeoJSON-driven region lookup to label epicentral areas in multiple languages.
- Bundled Scratch project files for verifying feature parity with the original visual implementation.

## Getting Started

### Prerequisites
- Python 3.9 or later on Windows/macOS/Linux
- `pip` for dependency installation
- Optional: `git` if you plan to pull updates to the dataset repository

### Installation
```bash
cd F:\ComputerLanguage\code\earthquake\earthquake_sim
python -m venv .venv
.venv\Scripts\activate           # Windows PowerShell/cmd
pip install -r requirements.txt
```
(Use `source .venv/bin/activate` on macOS/Linux.)

### Usage
```bash
cd F:\ComputerLanguage\code\earthquake\earthquake_sim
python main.py
```
- Click on the map or use arrow keys to set latitude/longitude.
- Adjust depth with `D/F`, magnitude with `M/N`, then press `Enter` to start the simulation.
- During the run: `Space` pauses, `R` resets, `+/-` changes playback speed.

## Development

### Available Scripts
- `python main.py` &mdash; launches the simulator window using the current configuration.
- No npm/Node scripts are defined; Python is the sole runtime.

### Development Workflow
1. Ensure the `JMA_Region-main/震央地名.geojson` path remains valid (the simulator auto-loads relative to `main.py`).
2. Modify domain logic inside `earthquake.py` / `intensity.py` as needed.
3. Run `python main.py` frequently to verify visual behavior; adjust constants in `config.py` for tuning.
4. If you edit the Scratch project, re-export `.sb3` files and optionally refresh `sb3_v2/project.json` for side-by-side comparison.

## Configuration
- `earthquake_sim/config.py` centralizes wave speeds, Earth geometry approximations, window size, FPS, and map bounds covering Japan.
- Color definitions (`INTENSITY_COLORS`) align with JMA standards and can be extended if new scales are required.
- No environment variables are currently used; all configuration lives in the Python module.

## Architecture
The simulator follows a lightweight modular design:
- **Earthquake** (model) tracks epicenter parameters and computes wave radii/arrival times.
- **Intensity utilities** convert magnitude/depth/distance or PGA into JMA intensity levels and colors.
- **EpicenterLocator** and **MapRenderer** both consume GeoJSON polygons to provide textual labels and draw map outlines, respectively.
- **EarthquakeSimulator** (in `main.py`) orchestrates user input, simulation timing, and rendering. Pygame surfaces serve as the rendering backend.
- Scratch assets (`sb3_v2`) serve as a fidelity reference rather than runtime dependencies.

## Contributing
No formal guidelines are provided. Recommended steps:
1. Fork or create a branch.
2. Keep GeoJSON data and Scratch assets untouched unless updates are verified.
3. Follow Python best practices (PEP 8, type hints, docstrings) when adding modules.
4. Test interactively before submitting patches or sharing builds.

## License
- The bundled `JMA_Region-main` dataset declares [CC0 1.0 Universal](JMA_Region-main/LICENSE).
- The Python simulator and Scratch recreations do not currently specify a license; consult the project owner before redistribution.
