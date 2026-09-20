# Playwright visual browsing: view and save

Deployed and verified 2026-09-19 (Vancouver time).

| Tool | Result | Artifact |
| --- | --- | --- |
| `browser_view_screenshot` | Native MCP pixels for Qwen | Automatically saved |
| `browser_save_screenshot` | File path only | Chosen or automatic name |

The legacy `browser_take_screenshot` is unchanged on the server but excluded from
OpenWebUI's selected tools. Qwen's system prompt now prefers view and explains
save plus terminal inspection; the filename workaround is gone. Responses
remains the provider protocol.

## Shared files

Playwright and the active `open-terminal` container see the same directory:
`/home/user/Pictures/Screenshots`.
Host storage remains `~/scripts/playwright-mcp/artifacts`.
The user's personal host Pictures library is not mounted. No shared filesystem
is required in OpenWebUI or llama.cpp; those receive image bytes over their APIs.

## Verified with Qwen

The original live view/save check established:

- View: Qwen chose `browser_view_screenshot`, received `input_text` + `input_image`,
  and read the new canvas code `JUNIPER-852` and `Waiting for a click`.
- Save: `browser_save_screenshot` returned text only and created
  `terminal-screenshot-check.png` (1920×1080).
- Qwen used ImageMagick through the terminal to create
  `terminal-screenshot-check-half.png` (960×540), retaining the original.
- Terminal `read_file` produced `input_text` + `input_image`; Qwen read
  `COPPER-417` and `Waiting for a click` from the processed image. The PNG was
  independently inspected and matched. No page-source fallback was used in this
  successful test.

The first live attempt lost its MCP session after navigation and was stopped.
A new chat and a direct HTTP SDK probe succeeded. The timing matches upstream's
five-second heartbeat deadline, although the cause was not conclusively proven.
The deployment now sets `PLAYWRIGHT_MCP_PING_TIMEOUT_MS=30000` to tolerate brief
client stalls; subsequent save/process/read verification passed. The temporary
fixture server on port8932 was stopped after the checks.

## Code, checks, and maintenance

Source: `~/Devel/playwright-mcp`, branch `feat/local-screenshot-tools`,
initially based on `f1257a5a67aff872f947fae274759f7d54853862`. The small
build-time patch modifies only the pinned
Playwright bundle's screenshot module. No MCP proxy or another full monorepo
checkout is involved. See `LOCAL_SCREENSHOT_TOOLS.md` there.

Image: `playwright-mcp:local-screenshot-tools`.
Rebuild/reapply: `~/scripts/playwright-mcp-install.sh` (0755).
The build checks the original bundle hash and refuses unexpected upstream code.

Seven real MCP/Chromium regression groups passed: tool/schema registration,
view pixels and saved bytes, named/unnamed save, full-page/element captures,
invalid arguments, legacy/JPEG behavior, and global image suppression. A separate
check confirmed patch rejection without writing on an unexpected bundle. Actual
Streamable HTTP was also checked from the OpenWebUI container.

No open-terminal source code was changed. The terminal's writable layer contained
installed software, so recreation used a
local committed image. Independent comparison confirmed configuration, secrets,
ports, network aliases, Documents mount, and the named home volume were preserved.
Its canonical Compose file was updated only for the rest service's image and
new bind. Both active containers are healthy with `unless-stopped` restart policy.

No llama.cpp changes or additional OpenWebUI code changes were needed; its local
visual-browser documentation was updated.

## Rollback

Terminal: `~/scripts/recreate-open-terminal-screenshots.sh --rollback`.
The original is retained as `open-terminal-before-screenshots-20260920-025754`.

Private backup journals and the terminal snapshot image contain existing local
configuration and are not included in this repository. The source and deployment
recipes do not require the original scratch directory. See [the maintenance
index](README.md#rollback-and-private-runtime-state) for the complete rollback
map and the distinction between reverting the tools and reverting storage routing.
Artifacts remain in the same host directory. Deployment details are also in
`~/scripts/playwright-mcp/README.md`.

## Final screenshot/diagnostics separation

The view/save tools now honor `PLAYWRIGHT_MCP_SCREENSHOT_DIR` for their image
files. Deployment still shares `/home/user/Pictures/Screenshots` with the terminal,
but stock `--output-dir` is `/home/user/.cache/playwright-mcp`, backed by
`~/scripts/playwright-mcp/cache`. The generic cache's 256 MiB cleanup does
not touch screenshots. Screenshots remain until manually removed.

Automatic accessibility YAML is disabled with `--snapshot-mode none`; explicit
`browser_snapshot` still works inline. Two native tools were added to OpenWebUI's
filter (19 selected tools): `browser_console_messages` and
`browser_network_requests`. Without filename they return actual diagnostics,
so Qwen does not need terminal log-file access. The system prompt records this.
Operation failures and page error counts remain in ordinary MCP responses.

The final browser-diagnostics check passed through Responses: Qwen read `ORCHID-629` and the teal circle, correctly
reported intentional warning/error messages and HTTP 503 for `/expected-failure`,
and saved `diagnostics-check.png`. Independent inspection confirmed the image,
only two PNGs in Screenshots, one console log in cache, and no YAML. No terminal
or source-reading fallback was used. Her extra approximate circle-size estimate
was inaccurate; precise visual measurements are still outside this acceptance test.

The expanded 14-group MCP/Chromium suite passes. Source includes a credential-free
`local/compose.example.yml` and ignores its runtime storage directories. Both
source repositories and the local deployment README have maintenance notes; the
master index is [README.md](README.md).

The previous local image is retained as
`playwright-mcp:before-cache-separation-20260919`; the matching older Compose
configuration was backed up privately. The maintenance index describes its
relevant settings so ordinary maintenance is not dependent on scratch files.
Use the retained image and matching configuration together when reverting only
this separation, and reapply with `--pull never`.
