# Current browser artifacts: screenshots, PDF previews, and shared Downloads

Updated 2026-09-19 (Vancouver time). This supersedes the two-tool view/save
experiment described in the historical status files.

## Contract

- `browser_take_screenshot` saves a file and returns pixels, with or without a
  filename. Existing global `--image-responses allow` includes pixels; `omit`
  suppresses them without affecting saving. We deploy `allow`.
- `browser_pdf_save` prints the current webpage to PDF, saves it, and returns its
  path plus a bounded preview of page images when image responses are enabled.
- `browser_pdf_read` renders an existing saved or downloaded PDF, including later
  page windows, without needing an active browser page. A download itself still
  returns a path; use this reader to inspect it.
- PDF previews follow the same global image policy as screenshots. With `omit`,
  the original file remains available and no preview images are returned.
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

## PDF rendering policy

Both PDF tools accept optional `startPage` (1-based, default 1) and `maxPages`.
The save tool's filename remains optional; the reader requires the saved path.
Results report the source-page window and total page count, label each returned
image with its original page number, list sparse pages omitted from the preview,
and give the next reader call when more pages remain. The window counts all
source pages examined, including omitted ones. Reading more pages does not
reprint or redownload the document.

These environment variables belong to the Playwright service:

| Setting | Default | Purpose |
| --- | --- | --- |
| `PLAYWRIGHT_MCP_PDF_DPI` | `96` | Render resolution; not exposed as a tool argument |
| `PLAYWRIGHT_MCP_PDF_MAX_PAGES` | `20` | Default and hard maximum source-page window per call |
| `PLAYWRIGHT_MCP_PDF_MIN_PAGE_BYTES` | `6144` | Minimum compressed PNG size for a preview; `0` disables filtering |

96 DPI makes a Letter page 816 × 1056 pixels, balancing whole-page legibility
against the payload of up to twenty images. Dense fine print may justify an
operator setting of 150 DPI (1275 × 1650), with the size threshold retuned too.
The model can choose fewer pages or a later starting page; it cannot change DPI
or the sparse-page policy.

The size filter deliberately follows the `geode-fin` rationale: tracking pixels
and nearly white pages can confuse vision models. Compressed PNG size is a cheap
proxy for visual information, not proof of blankness. The default aims to retain
even one word such as “hello” while dropping near-white pages at 96 DPI with the
pinned encoder. Fonts, page dimensions, DPI and encoder changes affect that
heuristic. Skips are explicit and preserve source numbering; the original PDF
is never altered. Operators can disable or retune the filter.

Rendering uses PDF.js and `@napi-rs/canvas`, without an intermediate transcription
model. Native MCP page-image blocks go through the existing OpenWebUI Responses
pipeline. The PNG previews are not additional files in Downloads. Input is capped
at 50 MiB and rendered pages at 20 million pixels with a 16,384-pixel dimension
limit. Read paths must stay within the artifact root and upstream allowed roots,
including symlink checks. Errors return as text, not error images; a failed
preview leaves a successfully saved PDF available at its returned path.

## Implementation and configuration

The Playwright branch remains `feat/local-screenshot-tools` for continuity. Its
checked bundle patch now removes the filename condition around image registration,
uses a shared artifact resolver, and routes attachment downloads through it. PDF
tool registration and image captions connect the bounded renderer to native MCP.
The extra `browser_view_screenshot` and `browser_save_screenshot` tools are gone.
`PLAYWRIGHT_MCP_ARTIFACT_DIR` replaces `PLAYWRIGHT_MCP_SCREENSHOT_DIR`.

The renderer and result adapter are `local/pdf-renderer.mjs` and
`local/pdf-preview.cjs` in the Playwright fork. `local/package.json` and its lock
pin `pdfjs-dist` 6.1.200 and `@napi-rs/canvas` 1.0.2. The image installs those
dependencies during its build. Dependency upgrades need the rendering and
sparse-page checks as well as the checked bundle patch.

The artifact directory must be absolute and within upstream allowed roots. The
working directory is Downloads, which satisfies that requirement. Relative and
automatic names resolve there; absolute filenames must stay within it. Lexical
and symlink escapes are rejected, including links into the cache. With the
variable unset, upstream save destinations apply. Arbitrary filesystem writes
from browser_run_code are outside this contract; that tool is not exposed.

OpenWebUI's MCP filter has 19 tools: the previous 18-tool Downloads setup plus
`browser_pdf_read`. Replace the two custom screenshot tools with
`browser_take_screenshot` if upgrading directly from the earlier experiment.
PDF, wheel/coordinate, console and network tools remain enabled. The PDF schemas
explain source-page selection; the model prompt can stay short:

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

## PDF preview acceptance

The installed revision passed 31 regression groups: 10 existing screenshot/artifact
MCP groups, 9 renderer groups, and 12 PDF MCP/Chromium groups. These include 96/150
DPI, default 20-of-22-page coverage and continuation, source page numbering, sparse
filtering that retains a single word, disabled filtering, malformed input, path
and symlink confinement, global image omission, retained saves after preview
failure, and continuation when human-facing paths are relative.

Live OpenWebUI/Qwen acceptance used only browser navigation, `browser_pdf_save`
with `maxPages: 1`, and `browser_pdf_read` for source page 2. Qwen read the unseen
`WILLOW-817`/teal circle on page 1 and `AMBER-392`/orange shape on page 2 from native
PDF image results. It did not use screenshots, terminal image readers or DOM text.
Independent rendering of the saved PDF confirmed two 816 × 1056 previews at 96 DPI,
with the expected content and no skipped pages. This verifies the multimodal
path and continuation; it does not establish accuracy for every dense document.

The live service uses the three explicit PDF environment values above. The
preceding image is retained as `playwright-mcp:before-pdf-vision-20260919`, and its
Compose backup is private at `~/scripts/playwright-mcp/private-pdf-rollout/compose-before.yml`.
To roll back only PDF previews, deploy that prior image/configuration and remove
`browser_pdf_read` from the client filter; the Downloads mount remains the same.
The temporary acceptance fixture was stopped after testing.

## Validation record before PDF previews

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

That test predates PDF vision and claims no coordinate-estimation accuracy. The
OpenWebUI backend has no new changes; its previously passing 27-test baseline
and earlier saved-image replay tests remain documented in LOCAL_VISUAL_BROWSER.md.

The new renderer and MCP PDF suites are documented in the companion Playwright
`LOCAL_SCREENSHOT_TOOLS.md`; their results and live PDF read are recorded above.
