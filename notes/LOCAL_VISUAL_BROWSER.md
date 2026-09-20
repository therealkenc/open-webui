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

## Local Playwright screenshots and artifacts

The companion image now exposes one `browser_take_screenshot`. It returns native
pixels and saves a file regardless of whether a filename was supplied; the global
`--image-responses allow|omit` setting controls pixels. The earlier view/save
split was removed. `browser_pdf_save` now returns a saved PDF path and bounded
page previews under the same global image policy. `browser_pdf_read` previews
saved/downloaded PDFs and later source-page windows without an active browser.

Playwright and open-terminal share `/home/user/Downloads`, backed by
`~/scripts/playwright-mcp/artifacts`. `PLAYWRIGHT_MCP_ARTIFACT_DIR` routes named
and automatic user exports there, while generic output/cache remains separate.
Terminal `read_file` can inspect saved images through the existing pipeline.
OpenWebUI and llama.cpp receive bytes through APIs and need no shared mount.
No additional OpenWebUI source change was needed for this revision.

The Playwright server defaults to 20 source pages per call at 96 DPI. Its
configurable compressed-PNG size threshold omits near-white previews that can
confuse vision models, while reporting skipped source pages explicitly. DPI and
the threshold are server settings, not model arguments. Page images use native
MCP content and the existing authorized image/history path above. The original
PDF is saved; preview PNGs are sent directly rather than added to Downloads.

See [current artifact setup](BROWSER_ARTIFACTS.md) for routing, deployment and
validation, and the companion `LOCAL_SCREENSHOT_TOOLS.md` for build/test details.
Historical tests from the two-tool experiment remain in
[the archived view/save record](playwright-view-save-status.md).

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
