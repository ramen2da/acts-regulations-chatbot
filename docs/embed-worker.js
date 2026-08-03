import { pipeline } from "https://cdn.jsdelivr.net/npm/@huggingface/transformers@4.0.1";

let extractorPromise = null;

function getExtractor() {
  if (!extractorPromise) {
    extractorPromise = pipeline("feature-extraction", CONFIG_EMBED_MODEL_ID, {
      dtype: CONFIG_EMBED_DTYPE,
      progress_callback: (p) => {
        self.postMessage({ type: "progress", progress: p });
      },
    });
  }
  return extractorPromise;
}

// config values are passed in via the init message instead of importing
// config.js directly, since module workers resolve relative imports
// against the worker's own URL.
let CONFIG_EMBED_MODEL_ID = "onnx-community/bge-m3-ONNX";
let CONFIG_EMBED_DTYPE = "q8";

self.onmessage = async (e) => {
  const { type, requestId } = e.data;

  if (type === "init") {
    CONFIG_EMBED_MODEL_ID = e.data.modelId;
    CONFIG_EMBED_DTYPE = e.data.dtype;
    return;
  }

  if (type === "embed_query") {
    try {
      const extractor = await getExtractor();
      const output = await extractor(e.data.text, { pooling: "cls", normalize: true });
      self.postMessage({ type: "embed_result", requestId, dense: Array.from(output.data) });
    } catch (err) {
      self.postMessage({ type: "embed_error", requestId, error: String(err) });
    }
  }
};
