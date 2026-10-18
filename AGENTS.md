# Project Agent Instructions

## Mac App Development Protocol

When changing this macOS app, follow this order:

1. Reproduce and locate the root cause before patching.
2. Prefer source-level validation before rebuilding the `.app`.
3. Do not run `./test_local_app.sh --rebuild` unless source changes must enter the bundled app.
4. Use `./test_local_app.sh` for normal local runs; it reuses the existing bundle and reduces TCC churn. Do not start local tests from Launchpad, Finder app lists, or `/Applications`.
5. Keep only one test copy of the app. Remove `/Applications/Mac截图语音工具.app` during local testing so it cannot conflict with `dist/Mac截图语音工具.app`.
6. Treat Accessibility, Input Monitoring, Screen Recording, and Microphone permissions as TCC state tied to the app identity. A rebuild can invalidate prior grants when ad-hoc signed. After every rebuild, reset stale local permissions with `./reset_permissions.sh` before asking the user to re-grant permissions; `./test_local_app.sh --rebuild` should do this automatically.
7. Never claim macOS permissions can be silently granted by script. Scripts may reset TCC, call request APIs, or open System Settings only.
8. Gate protected features with preflight checks:
   - Accessibility: `AXIsProcessTrusted`
   - Input Monitoring: `CGPreflightListenEventAccess`
   - Input Monitoring request: `CGRequestListenEventAccess`
   - Screen Recording: `CGPreflightScreenCaptureAccess`
   - Screen Recording request: `CGRequestScreenCaptureAccess`
9. For screenshot features, never continue with a blank/desktop-only capture. If Screen Recording is not trusted, stop and guide the user.
10. Do not use `showFullScreen()` for screenshot overlays; it creates a macOS full-screen Space. Use a frameless always-on-top window sized to the current screen geometry.
11. For screenshots on Retina displays, map Qt logical coordinates to physical image pixels before cropping or drawing.
12. Avoid heavy work inside Qt mouse/key event handlers. Defer complex actions with `QTimer.singleShot(0, ...)`.
13. In packaged PyQt apps, unhandled exceptions in event callbacks can abort the process. Wrap risky callback bodies and keep event handlers small.
14. Treat `pynput` listeners as long-lived. Avoid repeated stop/start cycles; update hotkey config in place where possible.
15. Normalize control-character key events, e.g. `Control+C` may arrive as `"\x03"` instead of `"c"`.
16. Keep architecture boundaries explicit: `MainWindow` should trigger controllers, not own screenshot, hotkey, permission, recording, and editor logic all at once.
17. Before final handoff, run the narrowest relevant tests, then verify the actual packaged app only if the change is inside the bundle.

See `docs/mac-app-development-checklist.md` for the longer checklist and failure modes learned during this project.
