import { useState } from "react";
import {
  BarChart3,
  BookOpen,
  Bot,
  ChevronDown,
  FileText,
  GraduationCap,
  LayoutDashboard,
  Menu,
  NotebookPen,
  PanelLeftClose,
  Settings,
  Sparkles,
  Target,
  X,
} from "lucide-react";
import { NavLink, Outlet, useLocation } from "react-router";
import { useAuth } from "../context/AuthContext";

const navigation = [
  { to: "/", label: "Tableau de bord", icon: LayoutDashboard },
  { to: "/cours", label: "Mes cours", icon: BookOpen },
  { to: "/documents", label: "Documents", icon: FileText },
  { to: "/resumes", label: "Résumés et fiches", icon: NotebookPen, comingSoon: true },
  { to: "/quiz", label: "Quiz", icon: Target, comingSoon: true },
  { to: "/assistant", label: "Assistant intelligent", icon: Bot },
  { to: "/progression", label: "Ma progression", icon: BarChart3, comingSoon: true },
  { to: "/revisions", label: "Révisions", icon: Sparkles, comingSoon: true },
  { to: "/parametres", label: "Paramètres", icon: Settings },
];

const pageTitles = Object.fromEntries(navigation.map((item) => [item.to, item.label]));

export default function AppLayout() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [accountOpen, setAccountOpen] = useState(false);
  const { user } = useAuth();
  const location = useLocation();
  const initials = user.username.slice(0, 2).toUpperCase();

  return (
    <div className="app-shell">
      {mobileOpen && (
        <button
          className="sidebar-overlay"
          onClick={() => setMobileOpen(false)}
          aria-label="Fermer la navigation"
        />
      )}
      <aside
        className={`sidebar ${collapsed ? "sidebar--collapsed" : ""} ${mobileOpen ? "sidebar--mobile-open" : ""}`}
      >
        <div className="sidebar__header">
          <div className="brand">
            <span className="brand__icon">
              <GraduationCap size={23} />
            </span>
            {!collapsed && (
              <div className="brand__text">
                <strong className="brand__name">StudyAI</strong>
                <p className="brand__caption">Espace étudiant</p>
              </div>
            )}
          </div>
          <button
            className="icon-button sidebar__mobile-close"
            onClick={() => setMobileOpen(false)}
            aria-label="Fermer le menu"
          >
            <X size={20} />
          </button>
        </div>
        <nav className="sidebar__nav" aria-label="Navigation principale">
          {navigation.map(({ to, label, icon: Icon, comingSoon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              onClick={() => setMobileOpen(false)}
              title={collapsed ? label : undefined}
              className={({ isActive }) => `nav-link ${isActive ? "nav-link--active" : ""}`}
            >
              <Icon size={19} className="nav-link__icon" />
              {!collapsed && (
                <>
                  <span className="nav-link__label">{label}</span>
                  {comingSoon && <span className="nav-link__badge">Bientôt</span>}
                </>
              )}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar__footer">
          <button
            onClick={() => setCollapsed(!collapsed)}
            className="sidebar__collapse"
            aria-label={collapsed ? "Développer le menu" : "Réduire le menu"}
          >
            <PanelLeftClose
              size={17}
              className={collapsed ? "sidebar__collapse-icon--flipped" : ""}
            />
            {!collapsed && "Réduire"}
          </button>
        </div>
      </aside>
      <div className={`app-content ${collapsed ? "app-content--collapsed" : ""}`}>
        <header className="topbar">
          <div className="topbar__left">
            <button
              onClick={() => setMobileOpen(true)}
              className="topbar__menu-button"
              aria-label="Ouvrir la navigation"
            >
              <Menu size={20} />
            </button>
            <div>
              <p className="topbar__eyebrow">Espace d’apprentissage</p>
              <h2 className="topbar__title">{pageTitles[location.pathname] ?? "StudyAI"}</h2>
            </div>
          </div>
          <div className="topbar__account">
            <button
              onClick={() => setAccountOpen(!accountOpen)}
              className="topbar__account-button"
              aria-expanded={accountOpen}
              aria-label="Ouvrir le menu du compte"
            >
              <span className="topbar__avatar">{initials}</span>
              <span className="topbar__desktop-caption">
                <strong className="topbar__username">{user.username}</strong>
                <span className="topbar__account-caption">Compte local</span>
              </span>
              <ChevronDown size={16} className="topbar__desktop-caption muted" />
            </button>
            {accountOpen && (
              <div className="account-menu">
                <p className="account-menu__username">{user.username}</p>
                <NavLink
                  to="/parametres"
                  onClick={() => setAccountOpen(false)}
                  className="account-menu__link"
                >
                  Paramètres et déconnexion
                </NavLink>
              </div>
            )}
          </div>
        </header>
        <main className="main-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
