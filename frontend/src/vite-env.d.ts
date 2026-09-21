/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** "true" in the static demo build — see scripts/build-static-demo.sh */
  readonly VITE_STATIC_DEMO?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
