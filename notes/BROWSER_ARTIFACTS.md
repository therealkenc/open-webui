# Current browser artifacts: one screenshot tool and shared Downloads

Updated 2026-09-19 (Vancouver time). This supersedes the two-tool view/save
experiment described in the historical status files.

## Contract

- `browser_take_screenshot` saves a file and returns pixels, with or without a
  filename. Existing global `--image-responses allow` includes pixels; `omit`
  suppresses them without affecting saving. We deploy `allow`.
- `browser_pdf_save` saves a PDF and returns its path, without page images.
  Automatic PDF-to-vision handling is a separate future slice.
- Browser downloads and user-requested exports use the same artifact root.
- Playwright and open-terminal share `/home/user/Downloads`, backed by
  `~/scripts/playwright-mcp/artifacts`. Existing files were preserved. This is
  the container home, not the host user's personal Downloads folder.
- Generic output remains `/home/user/.cache/playwright-mcp`, backed by
  `~/scripts/playwright-mcp/cache`. Automatic logs and snapshots stay there.
  `--snapshot-mode none` disables automatic YAML; explicit snapshot/console/network
  requests without filename return inline. Explicitly saving them creates an
  artifact in Downloads.
- `--file-paths absolute` returns paths usable by the terminal. No model prompt
  needs to teach the directory. OpenWebUI and llama.cpp need no shared mount.

The separate roots are important: upstream cache eviction is recursive and must
not remove user artifacts. Downloads are retained until manually removed.

## Implementation and configuration

The Playwright branch remains `feat/local-screenshot-tools` for continuity. Its
checked bundle patch now removes the filename condition around image registration,
uses a shared artifact resolver, and routes attachment downloads through it.
The extra `browser_view_screenshot` and `browser_save_screenshot` tools are gone.
`PLAYWRIGHT_MCP_ARTIFACT_DIR` replaces `PLAYWRIGHT_MCP_SCREENSHOT_DIR`.

The artifact directory must be absolute and within upstream allowed roots. The
working directory is Downloads, which satisfies that requirement. Relative and
automatic names resolve there; absolute filenames must stay within it. Lexical
and symlink escapes are rejected, including links into the cache. With the
variable unset, upstream save destinations apply. Arbitrary filesystem writes
from browser_run_code are outside this contract; that tool is not exposed.

OpenWebUI's MCP filter has 18 tools: the previous set with the two custom
screenshot tools replaced by `browser_take_screenshot`. PDF, wheel/coordinate,
console and network tools remain enabled. The integration description reflects
the new contract. The model prompt stays short:

```text
When visual or interactive browsing is needed, use Visual Browser (Playwright). Use search_web to discover URLs and fetch_url for ordinary text. Use browser_take_screenshot to see page pixels directly. Screenshots are also saved; choosing a filename does not change the image response.
```

The viewport remains 1920×1080, scale defaults to CSS pixels, Responses and vision
remain enabled. The existing OpenWebUI image-forwarding code is unchanged.
Neither open-terminal nor llama.cpp needed source changes.

## Deployment and rollback

`~/scripts/playwright-mcp-install.sh` rebuilds the image and applies its Compose.
The portable source recipe is `local/compose.example.yml` in the Playwright fork.
The live image tag remains `playwright-mcp:local-screenshot-tools`.

Terminal migration used `~/scripts/recreate-open-terminal-downloads.sh --apply`.
It snapshots the writable layer, preserves credentials/environment, networking,
restart policy, named home volume and Documents bind, and replaces the old
Pictures/Screenshots mount with Downloads. The existing Downloads directory was
empty before mounting. Only the REST service in the canonical terminal Compose
was updated. The previous container is retained stopped, with restart disabled.

Rollback journal and matching old Playwright Compose are private under
`~/scripts/playwright-mcp/private-downloads-rollout`. Terminal rollback uses
`~/scripts/recreate-open-terminal-downloads.sh --rollback`; old Playwright image
is `playwright-mcp:before-downloads-20260919`. Reverting requires restoring the
matching two-tool filter/prompt and both mounts together. Never publish terminal
snapshot images or private rollback files; they preserve existing credentials.

## Validation

Ten isolated, real MCP/Chromium regression groups pass in the Playwright image,
covering named/automatic screenshots and PDFs, browser attachment downloads,
native image bytes and dimensions, full-page/element capture, JPEG inference,
inline diagnostics and explicit exports, automatic YAML/cache separation, global
image omission, unset-variable fallback, path/symlink confinement and root checks.
The patch also rejects an unexpected bundle before modification.

Live OpenWebUI acceptance: Qwen navigated to a local canvas fixture, took a
**named** `downloads-check.png`, read the previously unseen `COBALT-483` code and
teal circle from the native image, and saved `downloads-check.pdf`. Through the
terminal tools she verified the returned `/home/user/Downloads/...` paths and
sizes: PNG 36,329 bytes; PDF 41,054 bytes. Independent inspection confirmed the
PNG content and a valid PDF header. Both files appeared in the OpenWebUI terminal
file panel. The fixture server was stopped after testing.

No PDF vision or coordinate-estimation accuracy is claimed by this test. The
OpenWebUI backend has no new changes; its previously passing 27-test baseline
and earlier saved-image replay tests remain documented in LOCAL_VISUAL_BROWSER.md.
