import { Navigate, Route, Routes } from 'react-router-dom'
import { useAuth } from './context/AuthContext'
import { LandingPage, AuthPage } from './pages/PublicPages'
import { AppLayout } from './layouts/AppLayout'
import { OverviewPage, NewAnalysisPage, NoticesPage, ResultPage, ChecklistPage, RemindersPage, AccessibilityPage, ProfilePage, AskPage, AdminPage } from './pages/DashboardPages'

function Protected({ children, admin = false }) {
  const { user, loading } = useAuth()
  if (loading) return <div className="page-loader"><div className="spinner" />Preparing your workspace…</div>
  if (!user) return <Navigate to="/signin" replace />
  if (admin && user.role !== 'admin') return <Navigate to="/app" replace />
  return children
}

export default function App() {
  return <Routes>
    <Route path="/" element={<LandingPage />} />
    <Route path="/signin" element={<AuthPage />} />
    <Route path="/signup" element={<AuthPage register />} />
    <Route path="/app" element={<Protected><AppLayout /></Protected>}>
      <Route index element={<OverviewPage />} />
      <Route path="new" element={<NewAnalysisPage />} />
      <Route path="notices" element={<NoticesPage />} />
      <Route path="notices/:id" element={<ResultPage />} />
      <Route path="checklists" element={<ChecklistPage />} />
      <Route path="reminders" element={<RemindersPage />} />
      <Route path="ask" element={<AskPage />} />
      <Route path="accessibility" element={<AccessibilityPage />} />
      <Route path="profile" element={<ProfilePage />} />
      <Route path="settings" element={<AccessibilityPage settings />} />
      <Route path="admin" element={<Protected admin><AdminPage /></Protected>} />
    </Route>
    <Route path="*" element={<Navigate to="/" replace />} />
  </Routes>
}
