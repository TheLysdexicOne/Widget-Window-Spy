# Square Tool

- Spawns in at size 64 x 64 which means the grid lines are at 4px intervals.
- Resize restricted to squares with grid snapping.
- This means the smallest it can be is 16 x 16 (1px grid lines)
- The largest it should be is 512 x 512 (32px grid lines)
- The tool should be able to be resized by dragging the corners.
- The tool should only be resizable into px squares that are multiples of the grid size.
- This means 16x16, 32x32, 64x64, 128x128, 256x256, and 512x512.
- Snaps to grid regardless if grid is visible or not.
- Alway snaps to grid
- The tool should be able to be moved around the canvas by dragging.
- Raw mouse input should be used to move the tool.
  - This means no "smoothing" of the mouse movement.
  - No mouse acceleration.
  - No "I think this might be helpful" extras
