# Local MCP image / Responses patch

Branch: `fix/mcp-responses-images`, based on `0a7c15832` (v0.11.3 backend).
See [the maintenance index](README.md) for the companion Playwright fork,
deployment map, and upstream merge procedure. This document describes the
OpenWebUI patch on the development branch.

Native MCP ImageContent previously reached the chat display as a saved file URL,
but the model-facing tool-output path only accepted inline data URLs. This patch
keeps an ordered image part referencing the same stored file, then resolves its
bytes with the existing file authorization checks immediately before inference.

Responses preserves images inside `function_call_output.output` for both
stateless continuation and saved-chat replay. Chat Completions deliberately moves
tool images into a subsequent user message. Normal execution and approval/resume
share output assembly. Stored chat output retains file references rather than
base64; a storage failure can fall back to inline data.

## Build

Run these commands from the repository root.

The overlay uses the exact existing upstream image, with identical backend code
at the base revision. It changes two Python modules and no schema or frontend.

```bash
docker build -f Dockerfile.local -t open-webui:local-responses-images .
```

This is a pinned local deployment recipe. When updating to a different upstream
release, update the base image and verify backend/dependency compatibility.

## Regression tests

The built image has the application dependencies. Tests use unittest, an isolated
temporary database, and no network or production data mount:

```bash
docker run --rm --network none --entrypoint python \
  -e DATA_DIR=/tmp/openwebui-tests \
  -e WEBUI_SECRET_KEY=disposable-test-key \
  -v "$PWD/backend/tests:/tests:ro" \
  open-webui:local-responses-images \
  -c 'import os, unittest; os.makedirs(os.environ["DATA_DIR"], exist_ok=True); result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.discover("/tests")); raise SystemExit(not result.wasSuccessful())'
```

27 tests cover native/embedded images, ordered mixed results, one-time file
storage, display references, Responses conversion and replay, preset connection
selection, access/read failures, text/audio compatibility, and Chat Completions.

Live validation used stock Playwright MCP, a 1920×1080 viewport, and local Qwen
through `/v1/responses`. Qwen read an unseen canvas code, then the exact changed
status after a measured click. A separate saved-image test survived browser
reload with the fixture server stopped and no further tool calls. Coordinate
estimation was intentionally excluded from this test.

## Local Playwright screenshot tools

The subsequently installed local Playwright image exposes `browser_view_screenshot`
(native pixels plus an automatically named file) and `browser_save_screenshot`
(file only, with optional name). OpenWebUI selects these instead of the original
`browser_take_screenshot`. The local Qwen instructions prefer viewing and identify
`/home/user/Pictures/Screenshots` as the browser/terminal shared screenshot directory.
Terminal `read_file` can inspect a saved or processed image through this same
multimodal pipeline. No additional OpenWebUI code change was needed.

The primary path is Playwright ImageContent → OpenWebUI stored image reference →
authorized bytes in a Responses `function_call_output` → llama.cpp/Qwen vision.
The optional file-processing path is save → terminal/ImageMagick → terminal
`read_file` → that same model-facing image pipeline. OpenWebUI and llama.cpp do
not need a bind mount of the screenshot directory.

The upstream 0.0.82 screenshot tool still omits ImageContent when `filename` is
specified. It remains available on the server for compatibility, but is no longer
exposed to Qwen. See `LOCAL_SCREENSHOT_TOOLS.md` in the companion Playwright MCP
repository for the small build patch and its protocol regression tests.

The deployed storage refinement separates screenshots from Playwright's generic
diagnostics. `PLAYWRIGHT_MCP_SCREENSHOT_DIR` targets
`/home/user/Pictures/Screenshots`, backed by
`~/scripts/playwright-mcp/artifacts`; generic output targets
`/home/user/.cache/playwright-mcp`, backed by
`~/scripts/playwright-mcp/cache`. `--snapshot-mode none` disables automatic
YAML snapshots while explicit `browser_snapshot` still returns inline text.
Native `browser_console_messages` and `browser_network_requests` provide inline
diagnostics when called without a filename. Fourteen Playwright MCP/Chromium
regression groups passed, including seven covering the refined storage and
diagnostics behavior; these are separate from the 27 OpenWebUI tests above.

Live Qwen validation used navigate, view, console, network, and save tools. It
read the unseen `ORCHID-629` code and teal circle from the screenshot, reported
the fixture's warning/error and deliberate HTTP 503 request, and saved
`diagnostics-check.png`. Independent inspection confirmed two PNGs in Screenshots,
one console log in the separate cache, and no YAML files. This confirms image and
diagnostics routing, not geometric or coordinate-estimation accuracy.

Page console logs are distinct from MCP operation failures and container logs.
Screenshots are user artifacts with manual cleanup; diagnostics/cache retention
is managed separately. Current deployment details and validation status belong
in the Playwright repository's `LOCAL_SCREENSHOT_TOOLS.md`.

## Patch boundary

The OpenWebUI source change consists of:

- `backend/open_webui/utils/middleware.py`: store MCP images once, preserve their
  ordered content, select the provider protocol, and resolve authorized image
  bytes before inference, including continuation and replay.
- `backend/open_webui/utils/misc.py`: preserve ordered multimodal tool output
  during message conversion; retain the Chat Completions fallback.
- `backend/tests/test_mcp_tool_images.py`, `test_tool_image_protocols.py`, and
  `test_tool_output_conversion.py`: the 27 regression cases.
- `Dockerfile.local` and `notes/`: build, deployment, and maintenance instructions.

Keep this boundary when updating the fork. Recheck the diff before committing;
do not add deployment launchers containing installation secrets,
database/upload backups, chat exports, private screenshots, or container inspect
files. The separate Playwright patch belongs in its own repository. No llama.cpp
change is needed for this work.

## Local deployment and rollback

The deployment command is recorded in `~/scripts/openwebui-install.sh`
(0755), which rebuilds this image and preserves the installation's existing
secret. Do not copy credentials from that script into this repository.

The original container is retained as `open-webui-before-visual-20260919` with
restart disabled. To roll back the application while preserving current data:

```bash
docker stop open-webui
docker rename open-webui open-webui-patched-stopped
docker rename open-webui-before-visual-20260919 open-webui
docker update --restart=always open-webui
docker start open-webui
```

The original data and launcher were backed up privately during deployment.
Those backups contain credentials and user data and are not source artifacts.
No data restore is needed for this patch's application rollback because it
changes no schema.
The provider setting remains Responses; switch it in Admin → Connections if
returning to Chat Completions. Avoid starting both containers against the data
directory concurrently.

No llama.cpp source change was required. No MCP compatibility wrapper is active.
