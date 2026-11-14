import { ArrowLeft, SearchX } from "lucide-react";
import { Link } from "react-router";

export default function NotFoundPage() {
  return (
    <div className="not-found">
      <div className="not-found__content">
        <span className="not-found__icon">
          <SearchX size={30} />
        </span>
        <p className="not-found__eyebrow">Erreur 404</p>
        <h1>Page introuvable</h1>
        <p>Cette adresse ne correspond à aucune page de StudyAI.</p>
        <Link to="/" className="button button--primary">
          <ArrowLeft size={17} />
          Retour au tableau de bord
        </Link>
      </div>
    </div>
  );
}
