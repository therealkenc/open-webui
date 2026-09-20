# Local Qwen visual browsing: maintenance notes

These notes document the work begun on 2026-09-19 (Vancouver time). They live in
this fork so the architecture, deployment choices, and upstream-merge checks
survive the original development session. The repositories are the source of
truth; exported patches and screenshots in a Codex scratch directory are not
required to maintain this work.

Start with [the OpenWebUI implementation](LOCAL_VISUAL_BROWSER.md) and
[the Playwright deployment record](playwright-view-save-status.md). The
[OpenWebUI validation record](openwebui-visual-browser-status.md) records the live
checks. The [historical investigation](openwebui-playwright-handoff.md) explains
the original failure and superseded approaches; it is not current setup guidance.

## Scope and architecture

| Component | Change | Responsibility |
| --- | --- | --- |
| OpenWebUI | Two backend utility modules, three test files, pinned overlay image | Preserve native MCP image results for the UI, history, and model |
| Playwright MCP | Checked build patch of the pinned screenshot module | Separate view/save tools and screenshot storage from generic output |
| open-terminal | Deployment configuration only: shared screenshot bind and local image snapshot | Optional file inspection and ImageMagick processing |
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

The optional processing path is `browser_save_screenshot` → terminal/ImageMagick
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

Playwright and open-terminal share `/home/user/Pictures/Screenshots`, backed by
`~/scripts/playwright-mcp/artifacts`. Playwright's generic output lives separately
at `/home/user/.cache/playwright-mcp`, backed by `~/scripts/playwright-mcp/cache`.
This is not the host user's personal Pictures library.

The local Playwright environment variable `PLAYWRIGHT_MCP_SCREENSHOT_DIR` routes
both new screenshot tools to the shared Pictures directory. Stock `--output-dir`
targets the generic cache, whose 256 MiB retention limit does not touch screenshots.
Keep those roots separate and non-nested. Screenshots require manual cleanup.
The generic directory may also contain downloads and PDFs; it is not exclusively
logs.

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
`local/patch-screenshot-tools.cjs`, `local/test-screenshot-tools.cjs`, a portable
`local/compose.example.yml`, and `LOCAL_SCREENSHOT_TOOLS.md`. Only the bundled
screenshot module is patched. Microsoft's original server entrypoint, transport,
and other handlers remain in use.

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
SHA-256 check. Inspect the new screenshot implementation before updating both
the image digest and patch hash. Check whether upstream now supplies equivalent
tools or settings, and prefer retiring local behavior where the invariants hold.
Do not just replace the hash to make the build pass. Preserve:

- View returns native pixels and an automatic saved copy, with no filename argument.
- Save returns a path without pixels; filenames affect storage, not tool identity.
- Legacy `browser_take_screenshot` behavior stays unchanged for other clients.
- Both new tools use upstream capture/encoding, scale, element/full-page validation,
  root checks, and symlink validation. Absolute and relative paths cannot escape
  the configured screenshot root; a symlink into the cache must also be rejected.
- Screenshots and generic-output cleanup remain separate. Native console/network
  tools and explicit snapshots work with automatic snapshots disabled.

Run from the Playwright checkout:

```bash
docker build -f Dockerfile.local -t playwright-mcp:local-screenshot-tools .
docker run --rm --network none --entrypoint node \
  -v "$PWD/local:/tests:ro" \
  playwright-mcp:local-screenshot-tools /tests/test-screenshot-tools.cjs
```

The recorded baseline is **14 passing real MCP/Chromium groups**, plus rejected
unexpected bundle input without modification, JavaScript syntax checks, and
Compose validation. These tests use a local HTTP fixture with no external network.

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

The pre-separation Playwright image was retained as
`playwright-mcp:before-cache-separation-20260919`. To revert just that refinement,
use its matching older Compose configuration: the earlier generic output and
working directory were both `/home/user/Pictures/Screenshots`, without the new
screenshot environment variable or `--snapshot-mode none`. This deliberately
restores mixed image/log/YAML output. Keep `--pull never` when deploying retained
local images. To revert the whole screenshot-tool addition, restore the stock
pinned image and select `browser_take_screenshot` in OpenWebUI again. See the
Playwright repository's maintenance note for the stock image pin.

Terminal rollback is recorded in
`~/scripts/recreate-open-terminal-screenshots.sh --rollback`. The original stopped
container is `open-terminal-before-screenshots-20260920-025754`. The canonical
terminal Compose file is under `~/Devel/geode-fin/tooling/terminal/`; only the
REST service image and screenshot bind changed. Preserve its existing environment,
secrets, ports, aliases, home volume, and Documents mount when recreating it.

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
