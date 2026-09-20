# Historical investigation: why MCP screenshots lost their pixels

Recorded 2026-09-19. **Superseded by the working implementation** described in
[LOCAL_VISUAL_BROWSER.md](LOCAL_VISUAL_BROWSER.md) and [the maintenance index](README.md).
This is retained as root-cause history, not a current task list or deployment guide.
The final deployment uses Responses and the separate view/save screenshot tools.

## Original failure

Stock Playwright MCP returned a native image block. OpenWebUI saved that image
and displayed it in the chat, yet the model received only text and a filename.
The model could already read the same PNG through a normal image attachment and
through direct vision input to the local llama.cpp endpoint. This isolated the
problem to native MCP result forwarding, not Qwen's vision encoder.

[OpenWebUI's documented behavior](https://docs.openwebui.com/features/extensibility/plugin/tools/#images-in-tool-results)
already described image parts in Responses tool output and a following user
image message for Chat Completions. The necessary conversion largely existed;
native image ingestion was losing the model-facing part before that conversion.
The upstream work in [commit 2a960a5](https://github.com/open-webui/open-webui/commit/2a960a59fe1dbbd35282f0556b3666d81102e781)
(referenced by [issue #29492](https://github.com/open-webui/open-webui/issues/29492)) was investigated, not blindly reapplied. The running
v0.11.3 container already contained that implementation. The clone at
`0a7c15832fb30b1903753e83f81dc7d27e5b0944` differed in CI, while the relevant backend
modules matched the running container. Rebuilding the unmodified clone could
not fix this particular failure.

At that baseline:

| Area | Failure or existing behavior |
| --- | --- |
| `utils/mcp/client.py` | Returned serialized MCP content blocks unchanged |
| `utils/middleware.py`: native image processing | Saved bytes and returned a relative `/api/v1/files/{id}/content` display URL |
| Embedded image-resource processing | Retained a `data:image/...` URL |
| Normal and approval/resume output assembly | Only `data:` image URLs became model `input_image` parts; native saved images were display-only |
| `utils/misc.py` | Already supported either flattening tool images into a user message or preserving multimodal parts |
| `routers/openai.py` | Already mapped tool content into Responses `function_call_output.output` |

A read-only diagnostic running the real processing/conversion functions with
mocked file persistence showed native ImageContent lost model pixels, whereas
identical embedded-resource bytes reached the conversion path. The final fix
preserves ordered image references and resolves authorized bytes at inference,
for ordinary execution, approval/resume, and saved-chat replay. It keeps UI images
and avoids storing duplicate base64 in chat output.

## Approaches deliberately left behind

An experimental MCP compatibility wrapper was rolled back. No wrapper is active;
the correction belongs in OpenWebUI's image pipeline. The local provider was
briefly switched to Chat Completions while investigating, then returned to
Responses for final acceptance. No llama.cpp changes were required.

A shared directory alone does not turn a filename into vision input. The existing
open-terminal integration does supply pixels through `read_file`, so shared
screenshots are useful for optional processing. That path was added as a secondary
capability, not as a workaround for broken direct MCP image forwarding.

The pinned Playwright MCP version treats an explicit screenshot filename as a
request to save without returning pixels. That behavior led to the later local
`browser_view_screenshot` / `browser_save_screenshot` split. The legacy tool remains
unchanged for other clients; do not reintroduce model instructions that depend on
omitting a filename once the two explicit tools are selected.

## Validation lessons worth preserving

The initial canvas fixture drew a teal circle, orange rectangle, purple triangle,
code `KITE-583`, and status `Waiting for a click`. Accessibility text could not
reveal those pixels. At the 1920×1080 viewport, a measured click at CSS coordinate
`(222,389)` changed the canvas to `Circle activated — success`.

Before the forwarding fix, the model sometimes claimed success despite not
receiving the image. Normal image upload and direct vision requests did work.
A guessed coordinate missed the circle; the measured coordinate succeeded and
the PNG was independently checked. Recognition, forwarding, and coordinate
estimation therefore require separate tests.

Final acceptance read new canvas codes through native MCP images, verified the
changed status after a measured click, and read an earlier image after chat reload
with the fixture stopped and no further tool call. It also confirmed image bytes
in the provider tool payload, visible chat images, and stored file references.
Later tests covered terminal image processing and inline browser diagnostics.
The live deployment uses Responses; Chat Completions compatibility is covered by
regression tests. Tests of visual transport are not proof of accurate autonomous
coordinate estimation or successful third-party chart rendering.

Use disposable data for a concurrent development instance. Never mount the live
OpenWebUI SQLite data into two running application instances. Preserve private
chat history, credentials, and image artifacts outside public source commits.
