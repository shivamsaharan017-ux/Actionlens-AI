import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { Accessibility, Activity, Bell, BookOpenCheck, ChevronDown, CircleHelp, FileClock, FilePlus2, Files, LayoutDashboard, LogOut, Menu, MoreHorizontal, Settings, ShieldCheck, UserRound, X, Sparkles } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { api } from '../services/api'

const baseLinks = [
  { to: '/app', label: 'Overview', icon: LayoutDashboard, end: true },
  { to: '/app/new', label: 'New analysis', icon: FilePlus2 },
  { to: '/app/notices', label: 'My notices', icon: Files },
  { to: '/app/checklists', label: 'Action checklists', icon: BookOpenCheck },
  { to: '/app/reminders', label: 'Reminders', icon: Bell },
  { to: '/app/ask', label: 'Ask AI', icon: CircleHelp },
]

export function AppLayout() {
  const { user, signOut } = useAuth()
  const [open, setOpen] = useState(false)
  const [bell, setBell] = useState(false)
  const [viewMenu, setViewMenu] = useState(false)
  const [reminderItems, setReminderItems] = useState([])
  const [reminderError, setReminderError] = useState('')
  const navigate = useNavigate()
  const location = useLocation()
  const title = location.pathname.includes('/new') ? 'New analysis' : location.pathname.includes('/notices/') ? 'Notice details' : location.pathname.includes('/notices') ? 'My notices' : location.pathname.includes('/checklists') ? 'Action checklists' : location.pathname.includes('/reminders') ? 'Reminders' : location.pathname.includes('/accessibility') ? 'Language & accessibility' : location.pathname.includes('/settings') ? 'Settings' : location.pathname.includes('/profile') ? 'Your profile' : location.pathname.includes('/ask') ? 'Ask AI' : location.pathname.includes('/admin') ? 'Institution dashboard' : 'Overview'
  const links = [...baseLinks, { to: '/app/accessibility', label: 'Language & access', icon: Accessibility }, { to: '/app/profile', label: 'Profile', icon: UserRound }, { to: '/app/settings', label: 'Settings', icon: Settings }, ...(user?.role === 'admin' ? [{ to: '/app/admin', label: 'Admin', icon: ShieldCheck }] : [])]
  const dashboardViews = [
    { to: '/app', label: 'Overview', icon: LayoutDashboard },
    { to: '/app/notices', label: 'My notices', icon: Files },
    { to: '/app/checklists', label: 'Action checklists', icon: BookOpenCheck },
    { to: '/app/reminders', label: 'Reminders', icon: Bell },
    { to: '/app/ask', label: 'Ask AI', icon: CircleHelp },
    { to: '/app/accessibility', label: 'Language & accessibility', icon: Accessibility },
    ...(user?.role === 'admin' ? [{ to: '/app/admin', label: 'Institution dashboard', icon: ShieldCheck }] : []),
  ]
  useEffect(() => {
    api.reminders().then(result => setReminderItems(result.items || [])).catch(() => {})
  }, [])
  useEffect(() => {
    if (!bell) return
    setReminderError('')
    api.reminders().then(result => setReminderItems(result.items || [])).catch(error => setReminderError(error.message))
  }, [bell])
  const now = new Date()
  const today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
  const activeReminders = reminderItems.filter(item => item.enabled).sort((a, b) => a.reminder_date.localeCompare(b.reminder_date))
  const dueReminders = activeReminders.filter(item => item.reminder_date <= today)
  return <div className="app-shell">
    <aside className={`sidebar ${open ? 'sidebar-open' : ''}`}>
      <div className="brand-row"><div className="brand-mark"><ScanMark /></div><span>actionlens<span className="brand-ai">.ai</span></span><button className="icon-button mobile-close" onClick={() => setOpen(false)} aria-label="Close navigation"><X size={19}/></button></div>
      <div className="workspace-label">WORKSPACE</div>
      <nav className="side-nav" aria-label="Main navigation">{links.map(({ to, label, icon: Icon, end }) => <NavLink key={to} to={to} end={end} onClick={() => setOpen(false)} className={({ isActive }) => `side-link ${isActive ? 'active' : ''}`}><Icon size={18} strokeWidth={1.8}/><span>{label}</span>{label === 'Ask AI' && <span className="new-dot"/>}</NavLink>)}</nav>
      <div className="sidebar-spacer" />
      <div className="support-card"><div className="support-spark"><Sparkles size={15}/></div><strong>Notice to action,<br/>made simple.</strong><span>Your AI companion for the fine print.</span><button onClick={() => navigate('/app/new')} className="support-link">Analyze a notice <span>↗</span></button></div>
      <div className="sidebar-user"><div className="avatar">{user?.name?.slice(0,1).toUpperCase() || 'A'}</div><div className="user-meta"><strong>{user?.name || 'ActionLens user'}</strong><span>{user?.role === 'admin' ? 'Administrator' : user?.email}</span></div><button className="icon-button user-logout" title="Sign out" onClick={signOut}><LogOut size={17}/></button></div>
    </aside>
    {open && <button className="mobile-scrim" onClick={() => setOpen(false)} aria-label="Close menu"/>}
    <main className="app-main">
      <header className="topbar"><button className="icon-button menu-trigger" aria-label="Open menu" onClick={() => setOpen(true)}><Menu size={20}/></button><div className="crumb"><span>Workspace</span><span className="crumb-slash">/</span><strong>{title}</strong></div><div className="top-actions"><div className="mode-pill"><span className="mode-dot"/>Private workspace</div><div className="view-menu-wrap" onBlur={e => { if (!e.currentTarget.contains(e.relatedTarget)) setViewMenu(false) }}><button className={`icon-button view-menu-button ${viewMenu ? 'selected' : ''}`} aria-label="Switch dashboard" aria-haspopup="menu" aria-expanded={viewMenu} title="Switch dashboard" onClick={() => { setViewMenu(!viewMenu); setBell(false) }}><MoreHorizontal size={20}/></button>{viewMenu && <div className="view-menu" role="menu"><span className="view-menu-label">SWITCH DASHBOARD</span>{dashboardViews.map(({ to, label, icon: Icon }) => <button key={to} role="menuitem" className={`view-menu-item ${location.pathname === to || (to !== '/app' && location.pathname.startsWith(`${to}/`)) ? 'current' : ''}`} onClick={() => { setViewMenu(false); navigate(to) }}><Icon size={15}/><span>{label}</span>{location.pathname === to && <i/>}</button>)}</div>}</div><div className="bell-wrap"><button className={`icon-button notification-button ${bell ? 'selected' : ''} ${dueReminders.length ? 'has-due' : ''}`} onClick={() => { setBell(!bell); setViewMenu(false) }} aria-label={`Notifications${dueReminders.length ? `, ${dueReminders.length} reminders due` : ''}`}><Bell size={18}/>{dueReminders.length > 0 && <i/>}</button>{bell && <div className="notification-pop"><div className="notification-pop-head"><strong>{dueReminders.length ? `${dueReminders.length} reminder${dueReminders.length === 1 ? '' : 's'} due` : 'Your reminders'}</strong><span className="reminder-count-badge">{activeReminders.length}</span></div>{reminderError ? <p>{reminderError}</p> : activeReminders.length ? <div className="notification-reminders">{activeReminders.slice(0, 3).map(item => <button key={item.id} className="notification-reminder" onClick={() => { setBell(false); navigate('/app/reminders') }}><span className={item.reminder_date <= today ? 'notification-due-icon' : 'notification-upcoming-icon'}><Bell size={13}/></span><span><strong>{item.title}</strong><small>{item.reminder_date <= today ? 'Due now' : `On ${new Date(`${item.reminder_date}T12:00:00`).toLocaleDateString()}`}</small></span></button>)}</div> : <p>You have no saved reminders yet. Add one to keep a next step in view.</p>}<button className="notification-view-all" onClick={() => { setBell(false); navigate('/app/reminders') }}>Manage reminders</button></div>}</div><button className="top-profile" onClick={() => navigate('/app/profile')}><div className="avatar small-avatar">{user?.name?.slice(0,1).toUpperCase() || 'A'}</div><ChevronDown size={15}/></button></div></header>
      <div className="page-area"><Outlet /></div>
    </main>
  </div>
}

export function ScanMark({ size = 18 }) { return <Activity size={size} strokeWidth={2.2} /> }
