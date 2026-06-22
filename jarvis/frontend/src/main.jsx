import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'

// StrictMode intentionally removed: it double-invokes effects in development,
// which causes the BootScreen progress intervals to run twice simultaneously,
// racing the progress to 100% before modules finish, and calling onComplete
// while the fade-out transition is mid-flight — resulting in a blank screen.
createRoot(document.getElementById('root')).render(<App />)
