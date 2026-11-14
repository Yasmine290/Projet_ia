import { ArrowRight, Construction } from "lucide-react";
import { Link, useLocation } from "react-router";
import { Button, Card, PageHeader } from "../components/ui";

const upcomingFeatures = {
  "/quiz": {
    title: "Quiz",
    description: "La création et l'enregistrement de quiz nécessitent encore un service backend.",
  },
  "/progression": {
    title: "Ma progression",
    description: "Le suivi de progression sera affiché lorsque les activités seront enregistrées.",
  },
  "/revisions": {
    title: "Révisions",
    description: "Les recommandations de révision seront ajoutées dans une étape ultérieure.",
  },
};

export default function ComingSoonPage() {
  const { pathname } = useLocation();
  const feature = upcomingFeatures[pathname] ?? {
    title: "Fonctionnalité à venir",
    description: "Cet espace n'est pas encore pris en charge par le backend.",
  };

  return (
    <div>
      <PageHeader eyebrow="Prochainement" title={feature.title} />
      <Card className="coming-soon-card">
        <span className="coming-soon-card__icon">
          <Construction size={27} />
        </span>
        <h2>Bientôt disponible</h2>
        <p>{feature.description} Aucune donnée fictive ne sera affichée dans cet espace.</p>
        <Link to="/assistant" className="button button--teal">
          Poser une question sur un cours <ArrowRight size={16} />
        </Link>
      </Card>
    </div>
  );
}
