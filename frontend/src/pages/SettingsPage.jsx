import { useState } from "react";
import { LogOut, ShieldCheck, UserRound } from "lucide-react";
import { useNavigate } from "react-router";
import { Button, Card, PageHeader } from "../components/ui";
import { useAuth } from "../context/AuthContext";

export default function SettingsPage() {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();
  const [submitting, setSubmitting] = useState(false);

  async function logout() {
    setSubmitting(true);
    try {
      await signOut();
      navigate("/connexion", { replace: true });
    } catch (requestError) {
      navigate("/connexion", {
        replace: true,
        state: {
          notice: `La session locale a été fermée, mais sa révocation par l’API a échoué : ${requestError.message}`,
        },
      });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div>
      <PageHeader
        eyebrow="Compte et sécurité"
        title="Paramètres"
        description="Consultez le compte connecté et mettez fin à sa session."
      />
      <div className="settings-grid">
        <Card className="settings-card">
          <div className="row settings-card__heading">
            <span className="settings-card__icon settings-card__icon--blue">
              <UserRound size={20} />
            </span>
            <div>
              <h2 className="settings-card__title">Compte StudyAI</h2>
              <p className="settings-card__description">Profil fourni par l’API authentifiée.</p>
            </div>
          </div>
          <dl className="account-detail">
            <dt>Nom d’utilisateur</dt>
            <dd>{user.username}</dd>
          </dl>
        </Card>
        <Card className="settings-card">
          <div className="row settings-card__heading">
            <span className="settings-card__icon settings-card__icon--teal">
              <ShieldCheck size={20} />
            </span>
            <div>
              <h2 className="settings-card__title">Session sécurisée</h2>
            </div>
          </div>
          <Button variant="danger" onClick={logout} disabled={submitting}>
            <LogOut size={16} />
            {submitting ? "Déconnexion…" : "Se déconnecter"}
          </Button>
        </Card>
      </div>
    </div>
  );
}
