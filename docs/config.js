const CONFIG = {
  // Reuses the existing yj-chatbot Cloudflare Worker as the Gemini proxy.
  // Its ALLOWED_ORIGINS must include this site's GitHub Pages origin.
  GEMINI_PROXY_URL: "https://yj-chatbot.bbuny006.workers.dev",

  // Must match scripts/config.py's EMBEDDING_MODEL so query and corpus
  // vectors live in the same space.
  EMBED_MODEL_ID: "onnx-community/bge-m3-ONNX",
  EMBED_DTYPE: "q8",

  TOP_K: 10,
  MANIFEST_URL: "./data/embeddings/manifest.json",
};
