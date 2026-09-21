import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'

function render() {
  ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>,
  )
}

// Static demo build: answer /api/* in the browser instead of calling a backend.
// Vite inlines the flag, so this branch and its JSON payload are dropped from
// the normal build entirely.
if (import.meta.env.VITE_STATIC_DEMO === 'true') {
  import('./api/staticDemo').then(({ installStaticDemo }) => {
    installStaticDemo()
    render()
  })
} else {
  render()
}
