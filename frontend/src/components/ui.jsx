import { LoaderCircle, X } from "lucide-react";

const buttonVariants = {
  primary: "button--primary",
  secondary: "button--secondary",
  teal: "button--teal",
  ghost: "button--ghost",
  danger: "button--danger",
};

const badgeTones = {
  teal: "badge--teal",
  blue: "badge--blue",
  amber: "badge--amber",
  red: "badge--red",
  slate: "badge--slate",
};

export function Button({
  children,
  variant = "primary",
  className = "",
  type = "button",
  ...props
}) {
  return (
    <button
      type={type}
      className={`button ${buttonVariants[variant] ?? buttonVariants.primary} ${className}`.trim()}
      {...props}
    >
      {children}
    </button>
  );
}

export function Card({ children, className = "" }) {
  return <section className={`card ${className}`.trim()}>{children}</section>;
}

export function Badge({ children, tone = "teal" }) {
  return <span className={`badge ${badgeTones[tone] ?? badgeTones.teal}`}>{children}</span>;
}

export function Field({ label, children, hint }) {
  return (
    <label className="field">
      <span className="field__label">{label}</span>
      {children}
      {hint && <span className="field__hint">{hint}</span>}
    </label>
  );
}

export const inputClass = "form-control";

export function EmptyState({ icon: Icon, title, description, action }) {
  return (
    <div className="empty-state">
      {Icon && (
        <span className="empty-state__icon">
          <Icon size={24} />
        </span>
      )}
      <h3>{title}</h3>
      <p>{description}</p>
      {action && <div className="empty-state__action">{action}</div>}
    </div>
  );
}

export function LoadingState({ label = "Chargement…" }) {
  return (
    <div className="loading-state" role="status">
      <LoaderCircle className="loading-state__icon" size={20} />
      {label}
    </div>
  );
}

export function Modal({ open, title, children, onClose, footer }) {
  if (!open) return null;
  return (
    <div
      className="modal-backdrop"
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-title"
      onMouseDown={(event) => event.target === event.currentTarget && onClose()}
    >
      <div className="modal">
        <div className="modal__header">
          <h2 id="modal-title">{title}</h2>
          <button onClick={onClose} className="icon-button" aria-label="Fermer">
            <X size={20} />
          </button>
        </div>
        <div className="modal__content">{children}</div>
        {footer && <div className="modal__footer">{footer}</div>}
      </div>
    </div>
  );
}

export function PageHeader({ eyebrow, title, description, action }) {
  return (
    <header className="page-header">
      <div className="page-header__main">
        {eyebrow && <p className="page-header__eyebrow">{eyebrow}</p>}
        <h1 className="page-header__title">{title}</h1>
        {description && <p className="page-header__description">{description}</p>}
      </div>
      {action && <div className="page-header__action">{action}</div>}
    </header>
  );
}
