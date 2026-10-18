# Mac App Development Checklist

This project hit several macOS-specific traps. Use this checklist before future Mac app changes.

## Build And Permissions

- Prefer source-level tests before rebuilding the app bundle.
- Use `./test_local_app.sh` for normal local runs.
- Use `./test_local_app.sh` to launch local tests; do not launch the development build from Launchpad, Finder app lists, or `/Applications`.
- Use `./test_local_app.sh --rebuild` only when edited source must be packaged into `dist/Mac截图语音工具.app`.
- After every rebuild, reset stale local TCC records with `./reset_permissions.sh` before asking the user to re-grant permissions. `./test_local_app.sh --rebuild` should run this automatically.
- Rebuilds with ad-hoc signing can change the app identity/cdhash and invalidate TCC permissions.
- Keep only one local app copy during testing. Remove `/Applications/Mac截图语音工具.app` when testing `dist/Mac截图语音工具.app`.
- Do not promise scripted permission grants. macOS requires user approval for protected capabilities.

## TCC Permission Gates

- Check Accessibility and Input Monitoring before relying on global hotkeys.
- Check Screen Recording before showing a screenshot overlay or accepting capture output.
- Call request APIs where available so the app appears in System Settings.
- If Screen Recording is missing, stop the workflow. Desktop-only or blank captures are failure states, not successful screenshots.

## Screenshot Architecture

- The desired model is a screenshot overlay:
  1. Capture current desktop.
  2. Show a frameless always-on-top overlay on the current Space.
  3. Let the user select a region in place.
  4. Keep the selected region at the same visual size.
  5. Place the toolbar near the selection.
  6. Block normal page interaction until copy/save/cancel.
- Do not implement screenshots as "capture file, then open a large white floating editor window".
- Do not use `showFullScreen()` for overlays; it can create a new macOS Space and make the display appear to change.
- Prefer native `screencapture -x` for the source desktop image over `QScreen.grabWindow(0)` when reliability matters.
- Map Qt logical coordinates to physical screenshot pixels on Retina displays.

## PyQt Stability

- Keep mouse/key event handlers thin.
- Defer complex work out of event handlers with `QTimer.singleShot(0, ...)`.
- Wrap risky callback bodies; packaged PyQt can abort on unhandled callback exceptions.
- Avoid mixing window hiding, native APIs, listener restarts, and screenshot operations in the same event stack.

## Hotkeys

- Global hotkeys that use `CGEventTapCreate` need both Accessibility and Input Monitoring permission.
- Avoid repeatedly stopping and starting `pynput` listeners.
- Update hotkey data in place where possible.
- Normalize control characters, e.g. `Control+C` can be reported as `"\x03"`.

## Architecture Rules

- `MainWindow` should trigger high-level actions only.
- Put screenshot selection/editing into a dedicated overlay/controller.
- Put permissions into permission helpers/services.
- Put global hotkeys into a dedicated controller.
- Put recording and recognition into separate voice controllers.
- Add tests for permission gates, coordinate mapping, and crash-prone event flows.

## Handoff Criteria

- Run relevant unit tests.
- Run `py_compile` for edited Python files.
- If the bundle was rebuilt, remind the user that TCC permissions may need to be refreshed.
- Check for new crash reports in `~/Library/Logs/DiagnosticReports`.
- Do not call a Mac app feature fixed until the code path is verified or the remaining blocker is clearly identified as TCC/system permission state.
