# Widget Window Spy

Professional screenshot analysis tool with coordinate tracking

## Project Structure

This project has been modularized following clean architecture principles:

```text
src/
├── core/               # Core business logic
│   ├── constants.py    # Application constants and configuration
│   ├── coordinates.py  # Coordinate system management
│   └── mouse_tracker.py # Real-time mouse position tracking
├── ui/                 # User interface components
│   ├── tracker_widget.py    # Main tracking window
│   └── screenshot_viewer.py # Screenshot analysis tool
├── utils/              # Utility functions
│   └── window_detection.py  # Window finding and analysis
└── main.py            # Application entry point
```

## Key Features

- **Real-time Coordinate Tracking**: Monitor mouse position across screen, window, and frame coordinate systems
- **Professional Screenshot Viewer**: Analyze screenshots with zoom, pan, grid overlay, and coordinate copying
- **Bbox Editing**: Draw and edit bounding boxes for automation development
- **Freeze Functionality**: Press Ctrl+F to freeze coordinate tracking for precise measurements
- **Multi-Monitor Support**: Works correctly across multiple monitor setups
- **Clipboard Integration**: Click to copy coordinates in various formats

## Architecture Principles

- **KISS (Keep It Simple)**: Manual selection over unreliable detection
- **DRY (Don't Repeat Yourself)**: Common patterns extracted to shared utilities
- **Clean Separation**: Core logic separated from UI components
- **Professional Standards**: Monospace fonts, consistent styling, proper error handling

## Running the Application

```bash
# Install dependencies
pip install -r requirements.txt

# Run with default target (WidgetInc.exe)
python src/main.py

# Run with custom target
python src/main.py --target MyApp.exe
```

## Development Notes

- All coordinates are frame-relative (0,0 = top-left of game area)
- Use `frame_to_screen_coords()` for screen operations
- Grid system uses 192x128 pixel art units
- Professional dark theme with precise coordinate formatting
- Thread-safe mouse tracking with Qt signals
