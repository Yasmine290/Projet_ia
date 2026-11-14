import { useState } from "react";
import { GraduationCap, ShieldCheck } from "lucide-react";
import { Navigate, useLocation, useNavigate } from "react-router";
import { Button, Card, Field, inputClass, LoadingState } from "../components/ui";
import { useAuth } from "../context/AuthContext";

export default function LoginPage() {
  const { user, loading, error: sessionError, signIn, register } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [mode, setMode] = useState("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [requestError, setRequestError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  if (loading) return <LoadingState label="Vérification de la session…" />;
  if (user) return <Navigate to="/" replace />;

  async function submit(event) {
    event.preventDefault();
    setRequestError("");
    setSubmitting(true);
    const credentials = { username: username.trim(), password };
    try {
      if (mode === "register") await register(credentials);
      await signIn(credentials);
      setPassword("");
      const destination = location.state?.from;
      navigate(destination?.startsWith("/") ? destination : "/", { replace: true });
    } catch (error) {
      setRequestError(error.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="auth-page">
      <div className="auth-card">
        <section className="auth-card__intro">
          <div className="brand">
            <span className="brand__icon">
              <GraduationCap size={27} />
            </span>
            <div>
              <h1 className="brand__name">StudyAI</h1>
              <p className="brand__caption">Espace étudiant</p>
            </div>
          </div>
          <div>
            <p className="auth-card__eyebrow">Apprendre avec ses propres documents</p>
            <h2>Votre espace de cours, en un seul endroit.</h2>
            <p>Importez vos documents, indexez-les et posez des questions à l’assistant local.</p>
          </div>
          <div className="auth-card__safety">
            <ShieldCheck size={19} />
            <p>Les cours et les documents sont isolés par compte sur le backend configuré.</p>
          </div>
        </section>

        <section className="auth-card__body">
          <div className="brand login-logo--mobile">
            <span className="brand__icon">
              <GraduationCap size={23} />
            </span>
            <h1 className="brand__name">StudyAI</h1>
          </div>
          <p className="page-header__eyebrow">Espace d’apprentissage local</p>
          <h2>{mode === "login" ? "Content de vous revoir" : "Créer un compte"}</h2>
          <p>
            {mode === "login"
              ? "Connectez-vous pour retrouver vos cours et documents."
              : "Votre compte protège vos cours et documents de ceux des autres utilisateurs."}
          </p>

          {(sessionError || requestError || location.state?.notice) && (
            <div className="notice notice--error" role="alert">
              {requestError || sessionError || location.state.notice}
            </div>
          )}

          <Card className="auth-card__form-card">
            <form className="auth-form" onSubmit={submit}>
              <Field label="Nom d’utilisateur">
                <input
                  className={inputClass}
                  autoComplete="username"
                  autoFocus
                  required
                  minLength={3}
                  maxLength={50}
                  pattern="[A-Za-z0-9_.-]+"
                  title="Utilisez de 3 à 50 caractères : lettres, chiffres, point, tiret ou souligné."
                  value={username}
                  onChange={(event) => setUsername(event.target.value)}
                />
              </Field>
              <Field
                label="Mot de passe"
                hint={
                  mode === "register"
                    ? "12 à 128 caractères."
                    : "Votre mot de passe de compte StudyAI."
                }
              >
                <input
                  className={inputClass}
                  type="password"
                  autoComplete={mode === "login" ? "current-password" : "new-password"}
                  required
                  minLength={mode === "register" ? 12 : 1}
                  maxLength={128}
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                />
              </Field>
              <Button type="submit" variant="teal" className="button--full" disabled={submitting}>
                {submitting
                  ? "Veuillez patienter…"
                  : mode === "login"
                    ? "Se connecter"
                    : "Créer mon compte"}
              </Button>
            </form>
          </Card>

          <p className="auth-switch muted small">
            {mode === "login" ? "Pas encore de compte ?" : "Vous avez déjà un compte ?"}{" "}
            <button
              type="button"
              className="text-button"
              onClick={() => {
                setRequestError("");
                setMode(mode === "login" ? "register" : "login");
              }}
            >
              {mode === "login" ? "Créer un compte" : "Se connecter"}
            </button>
          </p>
          <p className="auth-safety">
            Ne partagez jamais votre mot de passe ni votre jeton de session.
          </p>
        </section>
      </div>
    </main>
  );
}
