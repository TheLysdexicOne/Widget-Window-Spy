#!/usr/bin/env python3
"""
Setup script for Widget Window Spy project.
Handles dependency installation and environment setup.
"""

import subprocess
import sys
from pathlib import Path


def run_command(cmd, description):
    """Run a command and handle errors."""
    print(f"\n{description}...")
    try:
        result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        print(f"✓ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ {description} failed:")
        print(f"  Command: {cmd}")
        print(f"  Error: {e.stderr}")
        return False


def main():
    """Main setup function."""
    print("Widget Window Spy - Project Setup")
    print("=" * 40)

    project_root = Path(__file__).parent
    requirements_file = project_root / "requirements.txt"

    if not requirements_file.exists():
        print(f"✗ Requirements file not found: {requirements_file}")
        return 1

    # Install dependencies
    if not run_command(f'pip install -r "{requirements_file}"', "Installing dependencies"):
        print("\nFailed to install dependencies. Please check the error above.")
        return 1

    print("\n" + "=" * 40)
    print("Setup completed successfully!")
    print("\nTo run the application:")
    print("  python src/main.py")
    print("  python src/main.py --target YourApp.exe")
    print("\nOr use the batch file:")
    print("  start.bat")

    return 0


if __name__ == "__main__":
    sys.exit(main())
