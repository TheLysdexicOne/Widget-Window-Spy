#!/usr/bin/env python3
"""
Test script to verify the modular structure works correctly.
"""

import sys
from pathlib import Path

# Add src to path for testing
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))


def test_imports():
    """Test that all modules can be imported correctly."""
    print("Testing modular imports...")

    try:
        # Test core components
        from core.constants import APP_TITLE, TARGET_PROCESS_DEFAULT
        from core.coordinates import CoordinateSystem
        from core.mouse_tracker import MouseTracker

        print("✓ Core components imported successfully")

        # Test utilities
        from utils.window_detection import find_target_window

        print("✓ Utilities imported successfully")

        # Test basic functionality
        coord_system = CoordinateSystem()
        mouse_tracker = MouseTracker()
        print("✓ Objects created successfully")

        # Test coordinate system
        coord_system.update_frame_area({"x": 100, "y": 100, "width": 800, "height": 600})
        inside = coord_system.is_inside_frame(400, 300)
        print(f"✓ Coordinate system working: point inside frame = {inside}")

        print("\n" + "=" * 50)
        print("All modular tests passed! ✓")
        print(f"App Title: {APP_TITLE}")
        print(f"Default Target: {TARGET_PROCESS_DEFAULT}")

        return True

    except Exception as e:
        print(f"✗ Import test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Main test function."""
    print("Widget Window Spy - Module Structure Test")
    print("=" * 50)

    if test_imports():
        print("\nStructure verification complete. Ready to run application!")
        return 0
    else:
        print("\nStructure verification failed. Check imports and dependencies.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
