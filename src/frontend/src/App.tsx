import { BrowserRouter, Routes, Route, Navigate, useLocation, Link } from 'react-router-dom'
import { useState, useEffect } from 'react'
import Dashboard from './pages/Dashboard'
import RuleSetManage from './pages/RuleSetManage'
import SandboxRun from './pages/SandboxRun'
import ReportView from './pages/ReportView'
import appStyles from './App.module.css'

function useIsMobile() {
  const [isMobile, setIsMobile] = useState(window.innerWidth <= 768)
  useEffect(() => {
    const handler = () => setIsMobile(window.innerWidth <= 768)
    window.addEventListener('resize', handler)
    return () => window.removeEventListener('resize', handler)
  }, [])
  return isMobile
}

function MobileNav() {
  const [open, setOpen] = useState(false)
  const location = useLocation()
  const isActive = (path: string) => location.pathname === path

  return (
    <>
      <button
        className={`${appStyles.hamburger} ${open ? appStyles.hamburgerOpen : ''}`}
        onClick={() => setOpen(!open)}
        aria-label="菜单"
      >
        <span className={appStyles.hamburgerLine} />
        <span className={appStyles.hamburgerLine} />
        <span className={appStyles.hamburgerLine} />
      </button>
      {open && <div className={appStyles.mobileNavOverlay} onClick={() => setOpen(false)} />}
      <nav className={`${appStyles.mobileNavDrawer} ${open ? appStyles.mobileNavDrawerOpen : ''}`}>
        <div className={appStyles.mobileNavHeader}>
          <span className={appStyles.mobileNavTitle}>医保飞检演练</span>
          <button className={appStyles.mobileNavClose} onClick={() => setOpen(false)}>×</button>
        </div>
        <Link
          to="/dashboard"
          className={`${appStyles.mobileNavItem} ${isActive('/dashboard') ? appStyles.mobileNavItemActive : ''}`}
          onClick={() => setOpen(false)}
        >
          📊 仪表盘
        </Link>
        <Link
          to="/rules"
          className={`${appStyles.mobileNavItem} ${isActive('/rules') ? appStyles.mobileNavItemActive : ''}`}
          onClick={() => setOpen(false)}
        >
          📋 规则集管理
        </Link>
        <Link
          to="/sandbox/run"
          className={`${appStyles.mobileNavItem} ${isActive('/sandbox/run') ? appStyles.mobileNavItemActive : ''}`}
          onClick={() => setOpen(false)}
        >
          🚀 演练执行
        </Link>
      </nav>
    </>
  )
}

function App() {
  const isMobile = useIsMobile()

  return (
    <BrowserRouter>
      <div style={{ display: 'flex', minHeight: '100vh' }}>
        {/* 移动端顶部导航栏 */}
        {isMobile && (
          <div
            style={{
              position: 'sticky',
              top: 0,
              zIndex: 100,
              background: 'white',
              borderBottom: '1px solid #e5e7eb',
              padding: '8px 12px',
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
            }}
          >
            <MobileNav />
            <span style={{ fontSize: '16px', fontWeight: 600, color: '#1a1a2e' }}>
              医保飞检演练
            </span>
          </div>
        )}
        {/* 桌面端左侧导航（可在后续页面添加） */}
        {!isMobile && (
          <nav
            style={{
              width: '200px',
              background: 'white',
              borderRight: '1px solid #e5e7eb',
              padding: '16px 8px',
              flexShrink: 0,
            }}
            className={appStyles.desktopNav}
          >
            <div style={{ fontWeight: 700, fontSize: '16px', color: '#1a1a2e', padding: '8px 12px', marginBottom: '8px' }}>
              医保飞检演练
            </div>
            <Link to="/dashboard" style={{ display: 'block', padding: '10px 12px', color: '#374151', textDecoration: 'none', borderRadius: '6px' }}>
              📊 仪表盘
            </Link>
            <Link to="/rules" style={{ display: 'block', padding: '10px 12px', color: '#374151', textDecoration: 'none', borderRadius: '6px' }}>
              📋 规则集管理
            </Link>
            <Link to="/sandbox/run" style={{ display: 'block', padding: '10px 12px', color: '#374151', textDecoration: 'none', borderRadius: '6px' }}>
              🚀 演练执行
            </Link>
          </nav>
        )}
        <main style={{ flex: 1, minWidth: 0 }}>
          <Routes>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/rules" element={<RuleSetManage />} />
            <Route path="/sandbox/run" element={<SandboxRun />} />
            <Route path="/sandbox/run/:runId" element={<ReportView />} />
            <Route path="/reports/:runId" element={<ReportView />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}

export default App