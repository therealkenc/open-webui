# Visual browsing is working through Responses

> Historical record. The view/save experiment and Pictures/Screenshots routing
> below are superseded by [the current single-tool Downloads setup](BROWSER_ARTIFACTS.md).
> Preserve earlier validation as history; do not use it as current configuration.

Verified 2026-09-19. OpenWebUI runs `open-webui:local-responses-images`, and the
local Qwen provider uses `/v1/responses`. Native MCP screenshots reach Qwen as
multimodal tool results. No llama.cpp changes or MCP wrapper were required.

## Verification

- 27 regression tests pass against real application imports in an isolated Docker
  container. Ruff checks and formatting, shell syntax, and git whitespace checks pass.
- Qwen read a previously unseen canvas code, `CEDAR-924`, from a Playwright image.
- After a supplied, measured click at `(222,389)`, Qwen read the exact new status:
  `Circle activated — success`. The PNG was independently inspected.
- A separate screenshot was saved without transcription. After reloading the chat
  and stopping the fixture web server, Qwen read `MAPLE-761` from the persisted
  image without another tool call. Stored chat output contains authorized file
  references, not base64 image data.
- From an ordinary browsing request, Qwen opened Yahoo Finance's MSFT page, took
  an inline screenshot, and accurately described its layout and still-loading
  chart. The PNG was independently checked; chart rendering itself was not fixed.

Coordinate estimation was deliberately excluded. Chat Completions compatibility
is covered by tests; the live acceptance tests used Responses.

## Configuration and source

Repository: `~/Devel/open-webui`.
Branch: `fix/mcp-responses-images`, initially based on `0a7c15832` (v0.11.3 backend).
The local deployment uses `Dockerfile.local` on the exact previous upstream image.
[LOCAL_VISUAL_BROWSER.md](LOCAL_VISUAL_BROWSER.md) documents the design, test
command, rebuild, and rollback.

The executable `~/scripts/openwebui-install.sh` now records the rebuild
and launch commands. The current container restarts automatically with Docker.
Visual Browser (Playwright) is selected as a default tool for `qwen3.8-27b-local`.
Its model system prompt prefers `browser_view_screenshot` for immediate visual
inspection and `browser_save_screenshot` for artifacts or terminal processing.
The earlier filename workaround has been removed. The terminal capability
remains enabled; it was deselected only for the initial browser-only test chats.
Playwright still uses a 1920×1080 viewport and isolated contexts.

The local Playwright patch separates those two tools. View returns native pixels
and saves an automatic copy; save returns a file path with an optional chosen
name. The unchanged upstream `browser_take_screenshot` is excluded from Qwen's
selected tools. Playwright and open-terminal share
`/home/user/Pictures/Screenshots`, backed by
`~/scripts/playwright-mcp/artifacts`. OpenWebUI and llama.cpp receive image
bytes over APIs and need no shared mount.

Live follow-up validation succeeded: Qwen viewed an unseen canvas code through
the new view tool, then saved a different screenshot, resized it with ImageMagick,
and read its code through the terminal integration's existing `read_file` image
support. No additional OpenWebUI or llama.cpp changes were required. See
[view/save validation](playwright-view-save-status.md).

The subsequent diagnostics refinement is deployed and verified: generic output moves
to `/home/user/.cache/playwright-mcp` (host `scripts/playwright-mcp/cache`), while
`PLAYWRIGHT_MCP_SCREENSHOT_DIR` keeps screenshots in the shared Pictures directory.
Automatic YAML snapshots are disabled with `--snapshot-mode none`; explicit
snapshots remain inline. The native console and network tools are selected for
on-demand diagnostics. Fourteen Playwright MCP/Chromium regression groups pass,
along with bundle-hash rejection, syntax, and Compose checks. These are separate
from the OpenWebUI tests above.

In the Browser Diagnostics test,
Qwen read `ORCHID-629` and a teal circle from the image, reported the fixture's
warning/error and deliberate HTTP 503 request, and saved `diagnostics-check.png`.
Independent image and terminal-mount checks confirmed two PNGs in Screenshots,
one console log in the separate cache, and no YAML files. The browser container
is healthy. This validates routing and visibility; geometric estimates remain
outside the acceptance criteria.

For the full service map, fork maintenance instructions, SearXNG notes, and rebuild/rollback
entry points, see [maintenance index](README.md).

## Rollback

The old container is retained as `open-webui-before-visual-20260919`, stopped with
restart disabled. The data backup and old launcher are retained privately,
outside the source repository.
The patch makes no schema changes. Application rollback commands are in the
[LOCAL_VISUAL_BROWSER.md](LOCAL_VISUAL_BROWSER.md); do not run both containers against the
same data directory concurrently. The temporary test web server has been stopped.
