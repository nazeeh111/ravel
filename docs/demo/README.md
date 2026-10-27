# RAVEL launch demo

[Watch the 18-second MP4](../assets/demo.mp4) or view the [inline GIF](../assets/demo.gif). The desktop product screenshot is [inspector.png](../assets/inspector.png).

This is a silent launch montage made from actual local RAVEL inspector screenshots and original identity graphics. It is **not a real-time screen recording**. Search states are genuine browser captures; cuts omit waiting and typing. The native Python composition adds titles and transitions around those captures. It does not replace result text, latency, source references, cache size, model name, or any other UI values.

## Captured product behavior

The public fictional fixture is `examples/sample` (three files, eight chunks). These are a small functional demonstration, not benchmark results:

- `retry_with_backoff`, adaptive mode, budget 1200: planner selected lexical retrieval; top result was the function in `retry.py:5–13`. The captured query reported 118 ms and a serialized evidence bound of 1126 UTF-8 bytes.
- `How can I wait longer between temporary failures?`, adaptive mode, budget 2400: planner selected hybrid retrieval using the explicitly enabled local BGE model. Results included `retry.py:5–13` and `notes.md:1–14`. The captured first query reported 5222 ms, including local model startup, and an evidence bound of 1605 bytes.
- Source detail shows line ranges, observed calls and a freshness check. “Observed calls” is syntactic call evidence; it is not a resolved dependency graph.

The screenshots show the initial local fixture before Git initialization, so the UI accurately says “No Git revision.” Timings are individual observations with other local activity present. They are not representative latency claims or comparisons. Index and vector-cache storage exclude the separate downloaded model. Budget accounting uses serialized UTF-8 bytes as a conservative token upper bound, not an exact tokenizer count; protocol overhead is separate.

## Reproduce the product moments

After installing RAVEL, from the repository root:

```sh
ravel index examples/sample --semantic --download-model --materialize
ravel inspect --root examples/sample
```

The model option explicitly permits a one-time public model download. The inspector's searches run locally. Enter the two queries and budgets above. Results, timings and file revisions can differ as the engine and fixture change.

## Edit or render the video

`composition/timeline.json` is the scene manifest. `composition/render.py` contains the native Pillow/FFmpeg composition. Original browser captures are in `assets/`, including a mobile QA frame that is not used in the video. `capture.json` preserves hashes and provenance. No font files, music, or other third-party media are bundled.

Use Python with Pillow and an installed FFmpeg:

```sh
python composition/render.py /absolute/new-demo.mp4
python composition/render.py /absolute/new-preview.png --frame 8.5
```

The renderer refuses to overwrite outputs and stages the video until encoding succeeds. The initial successful render is preserved in `render-20261026/`. System fonts are used, with Linux fallbacks, so typography can vary across machines. The movie is 1280×720, 30 fps, H.264, 18.000 seconds, with no audio stream. The GIF is 960×540, 10 fps, 18.000 seconds.

## Verification

- Actual desktop searches and source passages were checked in the browser.
- The inspector was rendered at 390×844 and the temporary viewport override was reset afterward.
- Inspector JavaScript parses successfully.
- `ffprobe` verified duration, dimensions, codec and absence of audio.
- Full FFmpeg decode passed for both MP4 and GIF.
- Frames from the actual encoded MP4 at 0.5, 3.1, 8.5, 11.2 and 16 seconds were extracted; representative settled and transition frames were visually inspected.

Source screenshots remain unchanged. PNG screenshot delivery is a lossless format conversion of the authentic JPEG browser capture.
