# Local Qwen visual browsing: maintenance notes

## Current OpenWebUI update path (2026-09-24)

Local `main` now carries the MCP image patch and tracks `upstream/main`. The
installer at `~/scripts/openwebui-install.sh` builds the full checked-out
Dockerfile, runs the three regression suites, backs up `~/.open-webui`, and
replaces the container only after a successful build and test run. It keeps the
prior container for rollback and waits for the new one to become healthy.

From a clean `main` checkout, use `git pull` followed by the installer. An
upstream change touching the patch may require a merge resolution and test
review before installation. `Dockerfile.local` and the branch references below
record the original v0.11.3 overlay deployment; they are no longer the update
path for this installation. The branch, pinned image, and rollback descriptions
below describe that original deployment unless a later date is stated.

These notes document the work begun on 2026-09-19 (Vancouver time). They live in
this fork so the architecture, deployment choices, and upstream-merge checks
survive the original development session. The repositories are the source of
truth; exported patches and screenshots in a Codex scratch directory are not
required to maintain this work.

Start with [the OpenWebUI implementation](LOCAL_VISUAL_BROWSER.md) and
[the current artifact setup](BROWSER_ARTIFACTS.md). The
[OpenWebUI validation record](openwebui-visual-browser-status.md) records the live
checks. The [historical investigation](openwebui-playwright-handoff.md) explains
the original failure and superseded approaches; it is not current setup guidance.

## Scope and architecture

| Component | Change | Responsibility |
| --- | --- | --- |
| OpenWebUI | Two backend utility modules, three test files, pinned overlay image | Preserve native MCP image results for the UI, history, and model |
| Playwright MCP | Checked build patch of the pinned bundle, bounded PDF renderer | Filename-independent screenshot images, PDF page previews, and shared artifact exports |
| open-terminal | Deployment configuration only: shared Downloads bind and local image snapshot | Optional file inspection and ImageMagick processing |
| llama.cpp | No changes from this work | Existing fork already supports multimodal `/v1/responses` tool output |
| SearXNG | Container/configuration maintenance | URL discovery through OpenWebUI's `search_web` |

**No open-terminal source was changed.** Its existing `read_file` already returns
image bytes. A local snapshot of the old container preserved software installed
in its writable layer before adding the bind mount. That snapshot is private
runtime state, not another source fork to maintain.

The normal path is:

```text
Playwright MCP ImageContent
  → OpenWebUI stores an authorized file reference for display/history
  → resolves bytes just before provider inference
  → Responses function_call_output containing ordered text/image parts
  → local llama.cpp / Qwen vision
```

The optional processing path is saved screenshot → terminal/ImageMagick
→ terminal `read_file` → the same image forwarding path. OpenWebUI and llama.cpp
need no screenshot-directory mount. A path in plain tool text does not itself
supply pixels to the model. No MCP compatibility wrapper is active.

Search, ordinary text retrieval, visual inspection, and terminal processing are
separate capabilities. The local provider uses Responses, with native function
calling and vision enabled. Chat Completions compatibility remains supported by
placing images in a following user message when that protocol is selected.

## Deployment map

Paths beginning with `~/` describe this installation, not a universal prerequisite.

| Service | Local entry point | Persistent state |
| --- | --- | --- |
| `open-webui` | `http://localhost:8080`; `~/scripts/openwebui-install.sh` | Existing `~/.open-webui` mounted at `/app/backend/data` |
| `playwright-mcp` | `http://virbr0.therealkenc.com:8931/mcp`; `~/scripts/playwright-mcp-install.sh` | Compose in `~/scripts/playwright-mcp/docker-compose.yml` |
| `open-terminal` | Existing OpenWebUI terminal integration | Existing named home volume and Documents bind retained |
| `searxng-core` | `http://virbr0.therealkenc.com:8082/search`; `~/scripts/searxng-install.sh` | `~/scripts/searxng` and existing `core-data` volume |

Playwright and open-terminal share `/home/user/Downloads`, backed by
`~/scripts/playwright-mcp/artifacts`. Existing screenshots were preserved.
`PLAYWRIGHT_MCP_ARTIFACT_DIR` routes named and automatically named screenshots,
PDFs, explicit exports and browser downloads there. Screenshot pixels and PDF
page previews are returned regardless of filename with `--image-responses allow`.
`browser_pdf_read` inspects saved/downloaded PDFs and later page windows without
an active browser. The two-tool screenshot experiment was removed. See
[current setup](BROWSER_ARTIFACTS.md) for page limits, DPI, sparse-page filtering
and migration of the OpenWebUI tool filter to 19 tools.

Generic output remains `/home/user/.cache/playwright-mcp`, backed by
`~/scripts/playwright-mcp/cache`. Automatic logs and snapshots stay there.
Keep the roots separate and non-nested: the 256 MiB cache limit must not touch
saved artifacts. Downloads require manual cleanup. This is the terminal's home,
not the host user's personal Downloads directory.

`--snapshot-mode none` disables automatic accessibility YAML. Explicit
`browser_snapshot` still returns the tree inline without a filename. Native
`browser_console_messages` and `browser_network_requests` return diagnostics
inline without a filename. Console `.log` files contain visited-page messages
and JavaScript errors, not MCP-server or Docker process logs. Operation failures
already return MCP errors. Plain-text links to log files in responses do not
automatically fetch those files for a remote model.

The viewport is 1920×1080, scale defaults to CSS pixels, and contexts are isolated
per connection. Navigate at the start of a new turn. The deployment sets
`PLAYWRIGHT_MCP_PING_TIMEOUT_MS=30000` after an initial session loss consistent
with the stock five-second deadline; that cause was plausible, not proven.

## Source boundaries and upstream updates

Public development branches:
[therealkenc/open-webui: fix/mcp-responses-images](https://github.com/therealkenc/open-webui/tree/fix/mcp-responses-images)
and [therealkenc/playwright-mcp: feat/local-screenshot-tools](https://github.com/therealkenc/playwright-mcp/tree/feat/local-screenshot-tools).
The initial implementation commits are OpenWebUI `9cf317869` and Playwright
`3b23607`; subsequent documentation commits carry these maintenance records.
`origin` points to the personal fork over SSH; `upstream` retains the original
project remote. Both forks use the customized branches above as their default
branches, so a fresh clone includes these changes and notes. The original `main`
branches remain available as the initial upstream baselines.

| Repository | Development branch | Starting upstream commit |
| --- | --- | --- |
| `~/Devel/open-webui` | `fix/mcp-responses-images` | `0a7c15832fb30b1903753e83f81dc7d27e5b0944` (v0.11.3 backend) |
| `~/Devel/playwright-mcp` | `feat/local-screenshot-tools` | `f1257a5a67aff872f947fae274759f7d54853862` |

OpenWebUI changes are in [middleware.py](../backend/open_webui/utils/middleware.py)
and [misc.py](../backend/open_webui/utils/misc.py). Tests live in
[backend/tests](../backend/tests), and [Dockerfile.local](../Dockerfile.local)
provides the deployed overlay build. The tests exercise real application imports;
they do not merely repeat a copied helper.

Playwright MCP implementation lives in the upstream Playwright monorepo, shipped
here through `playwright-core`. Its fork contains `Dockerfile.local`,
`local/patch-screenshot-tools.cjs`, `local/pdf-renderer.mjs`,
`local/pdf-preview.cjs`, pinned rendering dependencies under `local/`, regression
suites, a portable `local/compose.example.yml`, and `LOCAL_SCREENSHOT_TOOLS.md`.
The bundled screenshot image policy, user-export resolver, browser-download
routing, PDF registration and image captions are patched. Microsoft's original
server entrypoint and transport remain in use.

For either repository, fetch and integrate upstream in an inspection branch from
the published development branch. For example, in OpenWebUI:

```bash
git status --short                 # Begin with a clean checkout.
git remote -v                    # upstream should be open-webui/open-webui.
git fetch upstream
git switch fix/mcp-responses-images
git switch -c maintenance/upstream-YYYYMMDD
git merge upstream/main
```

In Playwright use `feat/local-screenshot-tools` and upstream
`microsoft/playwright-mcp`. Choose a fresh maintenance branch name for each update.
Do not overwrite unrelated local work or force-push the published branch merely
to incorporate upstream. Review changes and run the checks below before merging
the maintenance branch back into the development branch and deploying it.

OpenWebUI merge invariants:

- Native MCP images and embedded image resources retain text/image order.
- Save each image once; keep a display/history file reference, and resolve its
  bytes with file authorization checks immediately before inference.
- Responses keeps pixels within `function_call_output.output`; continuation,
  approval/resume, and saved-chat replay use the same behavior.
- Chat Completions still gets its required user-image fallback. Text/audio tools
  and provider-connection selection must remain compatible.
- Do not put base64 into ordinary text or solve only the immediate live turn.

The overlay copies two Python files onto a pinned upstream image. When changing
upstream revision, update that base image to a matching backend/dependency set;
copying newer modules onto an arbitrary older release is not a valid upgrade.
The [OpenWebUI implementation note](LOCAL_VISUAL_BROWSER.md) has exact build/test
commands. The initial baseline is **27 passing regression tests**.

For Playwright, an upstream image change will deliberately fail the full-bundle
SHA-256 check. Inspect the new screenshot, artifact and PDF implementations before
updating both the image digest and patch hash. Check whether upstream now supplies equivalent
tools or settings, and prefer retiring local behavior where the invariants hold.
Do not just replace the hash to make the build pass. Preserve:

- One `browser_take_screenshot` returns native pixels with or without a filename;
  the upstream global image-response mode remains authoritative.
- Named and automatic screenshots/PDFs share Downloads. PDF saves return their
  path plus bounded native page previews when image responses are enabled.
- The PDF reader can inspect later windows and downloaded PDFs without a live
  browser. Source page labels, skip reports and continuation instructions retain
  original page numbering, including pages omitted from previews.
- Page limits count source pages examined. DPI and the compressed-PNG threshold
  remain operator settings, with documented near-white/tracking-pixel rationale.
  Preview failures return text and preserve saved PDFs; no error images.
- Capture/encoding, scale and element/full-page validation stay upstream.
- Artifact paths cannot escape the configured root, including through symlinks
  into the cache; upstream root checks remain enforced.
- Browser attachment downloads and explicitly saved exports use Downloads.
  Automatic diagnostics and their eviction stay separate; inline console/network
  and explicit snapshots still work with automatic snapshots disabled.

Run from the Playwright checkout:

```bash
docker build -f Dockerfile.local -t playwright-mcp:local-screenshot-tools .
docker run --rm --network none --entrypoint node \
  -v "$PWD/local:/tests:ro" \
  playwright-mcp:local-screenshot-tools /tests/test-screenshot-tools.cjs
docker run --rm --network none --entrypoint node \
  -v "$PWD/local/test-pdf-renderer.mjs:/app/local/test-pdf-renderer.mjs:ro" \
  playwright-mcp:local-screenshot-tools /app/local/test-pdf-renderer.mjs
docker run --rm --network none --entrypoint node \
  -v "$PWD/local:/tests:ro" \
  playwright-mcp:local-screenshot-tools /tests/test-pdf-tools.cjs
```

The current baseline is **31 passing groups**: 10 screenshot/artifact MCP groups,
9 PDF renderer groups and 12 PDF MCP/Chromium groups. Bundle rejection and Compose
validation also pass. These tests use local fixtures with no external network.
The live PDF save/read acceptance is recorded in BROWSER_ARTIFACTS.md.
Recheck sparse-page calibration when upgrading PDF.js/canvas or changing DPI:
compressed PNG size is a heuristic whose behavior depends on those choices.

Before deploying an upgrade, keep the previous image and configuration, check
`docker compose config --quiet`, and verify the live native HTTP transport from
OpenWebUI. Use separate test data if running a second OpenWebUI instance. Finish
with a canvas image containing a new code, a screenshot after a measured click,
and saved-chat image replay after stopping the fixture. Inspect the actual image;
a model's confident claim is not proof. Coordinate estimation is a separate test.

## Rollback and private runtime state

OpenWebUI's patch changes no schema. The retained original container is
`open-webui-before-visual-20260919`; application rollback commands are in
[LOCAL_VISUAL_BROWSER.md](LOCAL_VISUAL_BROWSER.md). Never run both containers
against the same data directory. The local launcher contains installation
credentials and is not an idempotent container replacement tool; inspect it
before rerunning, and do not publish it.

The preceding two-tool Playwright image is retained as
`playwright-mcp:before-downloads-20260919`. Its matching Compose backup is in
`~/scripts/playwright-mcp/private-downloads-rollout/playwright-compose-before.yml`.
Rolling back that experiment also requires its old client tool filter/prompt.
The new terminal migration helper is
`~/scripts/recreate-open-terminal-downloads.sh --rollback`; its private journal
is under the same private-downloads-rollout directory. The retained original is
`open-terminal-before-downloads-20260920-053607`. Roll back both mounts together
if needed. The canonical terminal Compose file remains under
`~/Devel/geode-fin/tooling/terminal/`; only the REST image and artifact bind change.
Preserve environment, credentials, installed programs, ports, aliases, home volume
and Documents mount. Local terminal image snapshots contain private configuration
and must never be published.

Private backups and rollback journals were made during the original session.
They are intentionally not included in this repository and must be retained
separately if a full data/configuration rollback is needed. No source build or
ordinary application rollback depends on a Codex Documents scratch directory.
Never publish database/upload contents, container inspect dumps, private screenshots,
chat exports, secrets, or the local terminal snapshot image as source artifacts.

## SearXNG maintenance recorded that evening

The deployment moved from `~/searxng` to `~/scripts/searxng`; its bind-mounted
configuration remains `./core-config:/etc/searxng` and its cache remains in the
existing `core-data` volume. The container upgraded from `2026.7.10-4abac08de` to
`2026.9.19-e831fc2a1`, pinned to digest
`sha256:547fdc19b45510ea1c0bc65ffadab3fcdde1ab1efd7fe696602284ba54d795ca`.
The published binding moved from `127.0.0.1:8082:8080` to
`192.168.122.1:8082:8080`; OpenWebUI uses `virbr0.therealkenc.com`.
Pulling `latest` does not replace the digest-pinned deployment until Compose is
intentionally updated.

Brave and DuckDuckGo were enabled, Google CSE retained, Bing disabled after
repeated irrelevant results, and a stale Mojeek override removed. Default
three-second engine timeouts, TLS verification, and automatic backoff remain.
Docker logs rotate at 10 MB with three files. OpenWebUI retains three search
results and its normal page retrieval integration.

Acceptance queries returned 32–39 results in 0.69–0.81 seconds with relevant
official pages first, and Qwen returned citations from `search_web`. DuckDuckGo
later presented a CAPTCHA while Brave and Google CSE still served results.
This is historical validation, not a guarantee of external engine availability;
container health alone does not establish search-engine health. The deployment
launcher records the actual Docker maintenance commands and original settings.

References: [SearXNG Docker documentation](https://docs.searxng.org/admin/installation-docker.html),
[Playwright MCP configuration](https://github.com/microsoft/playwright-mcp#configuration),
[Playwright MCP tools](https://github.com/microsoft/playwright-mcp#tools).
