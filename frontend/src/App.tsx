import { BrowserRouter, Navigate, Route, Routes, useParams } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext'
import Landing from './pages/Landing'
import AuthPage from './pages/AuthPage'
import ProjectsHub from './pages/ProjectsHub'
import WorkspacePage from './pages/WorkspacePage'

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

  return <WorkspacePage />
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
