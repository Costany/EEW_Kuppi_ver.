# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Interactive earthquake arrival-time simulator for Japan. Python/Pygame rewrite of the Scratch project "地震の到達時間シミュレーション". Visualizes P- and S-wave propagation, calculates JMA (Japan Meteorological Agency) seismic intensities, and renders Japan's map with epicenter region labeling.

## Commands

```bash
# Setup
cd earthquake_sim
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # macOS/Linux
pip install -r requirements.txt

# Run simulator
python earthquake_sim/main.py
```

## Architecture

```
earthquake_sim/
├── main.py          # EarthquakeSimulator class - pygame loop, UI, event handling
├── config.py        # Constants: wave speeds, window size, map bounds, intensity colors
├── earthquake.py    # Earthquake model - epicenter params, wave radius/arrival calculations
├── intensity.py     # JMA intensity formulas (distance attenuation, PGA conversion)
├── epicenter.py     # EpicenterLocator - GeoJSON point-in-polygon region lookup
└── map_renderer.py  # MapRenderer - draws GeoJSON polygons on pygame surface
```

Key data flow:
- `main.py` creates `Earthquake` instance with user-set lat/lon/depth/magnitude
- `Earthquake.update(dt)` advances time; `get_p_wave_radius()` / `get_s_wave_radius()` compute current wave fronts
- `EpicenterLocator` and `MapRenderer` both load `JMA_Region-main/震央地名.geojson` for region names and map outlines

## Key Constants (config.py)

- P_WAVE_SPEED: 7.3 km/s
- S_WAVE_SPEED: 4.1 km/s
- MAP_BOUNDS: Japan region (lon 122-154, lat 24-46)
- Window: 1200x800 @ 60 FPS

## Simulator Controls

- Arrow keys: adjust lat/lon
- D/F: adjust depth
- M/N: adjust magnitude
- Enter: start simulation
- Space: pause/resume
- R: reset
- +/-: change playback speed

## Package Management Rules

**IMPORTANT: All AI models must follow these rules when installing packages**

- **NEVER** use plain `pip install` or `python -m pip install`
- **MUST** use the virtual environment's Python interpreter
- **Windows**: Use `.venv\Scripts\python -m pip install package_name`
- **macOS/Linux**: Use `.venv/bin/python -m pip install package_name`
- If virtual environment is not activated, the command will be rejected

**Why:** This prevents accidentally installing packages to the system Python environment instead of the project's isolated virtual environment.

### Example
```bash
# CORRECT ✓
.venv\Scripts\python -m pip install pygame

# INCORRECT ✗
pip install pygame
python -m pip install pygame
```
