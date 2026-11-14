import { ArrowRight, BookOpen, FileText, Plus, Sparkles } from "lucide-react";
import { Link } from "react-router";
import { useStudyData } from "../context/StudyDataContext";
import { Badge, Button, Card, EmptyState, LoadingState, PageHeader } from "../components/ui";

const courseColors = ["#16a6a1", "#4f6fdd", "#8b5cf6", "#e8874a", "#d35676", "#55876b"];

function StatCard({ icon: Icon, label, value, hint, tone }) {
  return (
    <Card className="stat-card">
      <div className="row row--between">
        <div>
          <p className="muted small">{label}</p>
          <p className="stat-card__value">{value}</p>
        </div>
        <span className={`stat-card__icon stat-card__icon--${tone}`}>
          <Icon size={21} />
        </span>
      </div>
      <p className="stat-card__hint">{hint}</p>
    </Card>
  );
}

export default function DashboardPage() {
  const { courses, documents, loading, error, refresh } = useStudyData();
  const indexedCount = documents.filter((document) => document.status === "indexed").length;
  const pendingCount = documents.filter(
    (document) => document.status === "pending_indexing",
  ).length;

  if (loading) return <LoadingState label="Chargement de vos cours et documents…" />;

  return (
    <div>
      <PageHeader
        eyebrow="Espace d’apprentissage"
        title="Votre tableau de bord"
        description="Retrouvez vos cours, documents importés et activités disponibles."
        action={
          <div className="row dashboard-actions">
            <Link to="/documents">
              <Button variant="secondary">
                <Plus size={17} />
                Importer un document
              </Button>
            </Link>
            <Link to="/assistant">
              <Button variant="teal">
                <Sparkles size={17} />
                Poser une question
              </Button>
            </Link>
          </div>
        }
      />

      {error && (
        <div className="notice notice--error row row--between" role="alert">
          <span>{error}</span>
          <Button variant="secondary" onClick={refresh}>
            Réessayer
          </Button>
        </div>
      )}

      <section className="stats-grid" aria-label="Statistiques du compte">
        <StatCard
          icon={BookOpen}
          label="Cours"
          value={courses.length}
          hint="Vos espaces d’apprentissage"
          tone="teal"
        />
        <StatCard
          icon={FileText}
          label="Documents"
          value={documents.length}
          hint={`${indexedCount} indexé${indexedCount === 1 ? "" : "s"}`}
          tone="blue"
        />
        <StatCard
          icon={Sparkles}
          label="À indexer"
          value={pendingCount}
          hint="Indexez les documents pour interroger l’assistant"
          tone="amber"
        />
      </section>

      <div className="page-grid page-grid--two dashboard-grid">
        <Card className="dashboard-courses">
          <div className="dashboard-section-header">
            <div>
              <h2>Mes cours</h2>
              <p>Cours réellement enregistrés dans l’API</p>
            </div>
            <Link to="/cours" className="inline-link">
              Tous les cours <ArrowRight size={16} />
            </Link>
          </div>
          <div className="course-list">
            {courses.slice(0, 4).map((course, index) => {
              const documentCount = documents.filter(
                (document) => document.course_id === course.id,
              ).length;
              return (
                <Link key={course.id} to="/cours" className="course-tile">
                  <div className="row row--between">
                    <span
                      className="course-tile__icon"
                      style={{ backgroundColor: courseColors[index % courseColors.length] }}
                    >
                      <BookOpen size={19} />
                    </span>
                    <Badge tone="slate">#{course.id}</Badge>
                  </div>
                  <h3>{course.title}</h3>
                  <p>
                    {documentCount} document{documentCount === 1 ? "" : "s"}
                  </p>
                </Link>
              );
            })}
            {!courses.length && (
              <div className="course-list__empty">
                <EmptyState
                  icon={BookOpen}
                  title="Aucun cours pour le moment"
                  description="Créez un cours pour commencer à organiser vos documents."
                  action={
                    <Link to="/cours">
                      <Button variant="teal">Créer mon premier cours</Button>
                    </Link>
                  }
                />
              </div>
            )}
          </div>
        </Card>

        <Card className="dashboard-start">
          <div className="row dashboard-start__heading">
            <span className="stat-card__icon stat-card__icon--teal">
              <Sparkles size={19} />
            </span>
            <div>
              <h2>Bien démarrer</h2>
              <p>Un parcours basé sur vos données</p>
            </div>
          </div>
          <ol className="step-list">
            <li>
              <Badge tone={courses.length ? "teal" : "slate"}>1</Badge>
              <span>Créez un cours pour organiser vos supports.</span>
            </li>
            <li>
              <Badge tone={documents.length ? "teal" : "slate"}>2</Badge>
              <span>Importez puis indexez vos documents.</span>
            </li>
            <li>
              <Badge tone={indexedCount ? "teal" : "slate"}>3</Badge>
              <span>Posez vos questions et consultez les sources.</span>
            </li>
          </ol>
          <Link
            to={indexedCount ? "/assistant" : courses.length ? "/documents" : "/cours"}
            className="quick-link"
          >
            {indexedCount
              ? "Ouvrir l’assistant"
              : courses.length
                ? "Ajouter un document"
                : "Créer un cours"}
            <ArrowRight size={16} />
          </Link>
        </Card>
      </div>
    </div>
  );
}
