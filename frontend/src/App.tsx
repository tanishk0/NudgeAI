import { BrowserRouter, Navigate, Route, Routes, useParams, Link } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext'
import Landing from './pages/Landing'
import AuthPage from './pages/AuthPage'
import ProjectsHub from './pages/ProjectsHub'

function ProtectedWorkspaceGate() {
  const { user, loading } = useAuth()
  const { projectId } = useParams<{ projectId: string }>()

  if (loading) {
    return (
      <div className="flex h-screen w-full items-center justify-center bg-[#0b0c10] text-sm text-white/60">
        Loading workspace session...
      </div>
    )
  }

  if (!user) {
    return (
      <Navigate
        to={`/auth?redirect=${encodeURIComponent(`/workspace/${projectId || ''}`)}`}
        replace
      />
    )
  }

  return (
    <div className="flex h-screen w-full flex-col items-center justify-center bg-[#0b0c10] text-white px-6 text-center">
      <p className="font-mono text-xs text-[#ffb86c] uppercase tracking-wider">
        Authenticated Workspace Route Ready
      </p>
      <h1 className="mt-2 text-2xl font-semibold">Project: {projectId}</h1>
      <p className="mt-2 max-w-md text-sm text-white/60">
        Signed in as <span className="text-white">{user.email}</span>. Next up: Workspace Session API & Cursor-style Monaco IDE!
      </p>
      <Link
        to="/projects"
        className="mt-6 rounded-xl border border-white/15 bg-white/5 px-4 py-2 text-xs font-medium text-white hover:bg-white/10 transition-colors"
      >
        &larr; Back to Projects Hub
      </Link>
    </div>
  )
}

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/auth" element={<AuthPage />} />
          <Route path="/projects" element={<ProjectsHub />} />
          <Route path="/workspace/:projectId" element={<ProtectedWorkspaceGate />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}

export default App
