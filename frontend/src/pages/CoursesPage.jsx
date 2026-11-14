import { useMemo, useState } from "react";
import { BookOpen, FileText, Pencil, Plus, Search, Trash2 } from "lucide-react";
import { Link } from "react-router";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  Field,
  inputClass,
  LoadingState,
  Modal,
  PageHeader,
} from "../components/ui";
import { useAuth } from "../context/AuthContext";
import { useStudyData } from "../context/StudyDataContext";
import { coursesApi } from "../services/coursesApi";

const courseColors = ["#16a6a1", "#4f6fdd", "#8b5cf6", "#e8874a", "#d35676", "#55876b"];

export default function CoursesPage() {
  const { token } = useAuth();
  const { courses, documents, loading, error, refresh } = useStudyData();
  const [query, setQuery] = useState("");
  const [modal, setModal] = useState(null);
  const [form, setForm] = useState({ title: "", description: "" });
  const [requestError, setRequestError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const visibleCourses = useMemo(
    () =>
      courses.filter((course) =>
        `${course.title} ${course.description}`.toLowerCase().includes(query.toLowerCase()),
      ),
    [courses, query],
  );

  function openCreate() {
    setForm({ title: "", description: "" });
    setRequestError("");
    setModal({ type: "create" });
  }

  function openEdit(course) {
    setForm({ title: course.title, description: course.description });
    setRequestError("");
    setModal({ type: "edit", course });
  }

  async function saveCourse(event) {
    event.preventDefault();
    setRequestError("");
    setSubmitting(true);
    const changes = { title: form.title.trim(), description: form.description.trim() };
    try {
      if (modal.type === "edit") {
        await coursesApi.update(token, modal.course.id, changes);
      } else {
        await coursesApi.create(token, changes);
      }
      setModal(null);
      refresh();
    } catch (requestError) {
      setRequestError(requestError.message);
    } finally {
      setSubmitting(false);
    }
  }

  async function deleteCourse(course) {
    const linkedDocuments = documents.filter((document) => document.course_id === course.id);
    if (linkedDocuments.length) return;
    if (!window.confirm(`Supprimer le cours « ${course.title} » ?`)) return;

    setRequestError("");
    try {
      await coursesApi.remove(token, course.id);
      refresh();
    } catch (requestError) {
      setRequestError(requestError.message);
    }
  }

  if (loading) return <LoadingState label="Chargement de vos cours…" />;

  return (
    <div>
      <PageHeader
        eyebrow="Votre espace d’apprentissage"
        title="Mes cours"
        description="Organisez vos matières et retrouvez les documents associés."
        action={
          <Button variant="teal" onClick={openCreate}>
            <Plus size={17} />
            Créer un cours
          </Button>
        }
      />

      {(error || requestError) && (
        <div className="notice notice--error row row--between" role="alert">
          <span>{requestError || error}</span>
          {error && (
            <Button variant="secondary" onClick={refresh}>
              Réessayer
            </Button>
          )}
        </div>
      )}

      <Card className="courses-toolbar">
        <div>
          <h2 className="toolbar-title">{courses.length} cours</h2>
          <p className="toolbar-description">Enregistrés dans votre compte.</p>
        </div>
        <label className="search-control">
          <Search size={18} />
          <input
            className="form-control"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Rechercher un cours…"
            aria-label="Rechercher un cours"
          />
        </label>
      </Card>

      {visibleCourses.length ? (
        <div className="course-cards">
          {visibleCourses.map((course, index) => {
            const courseDocuments = documents.filter(
              (document) => document.course_id === course.id,
            );
            const indexedCount = courseDocuments.filter(
              (document) => document.status === "indexed",
            ).length;
            const color = courseColors[index % courseColors.length];
            return (
              <Card key={course.id} className="course-card">
                <div className="course-card__stripe" style={{ backgroundColor: color }} />
                <div className="course-card__body">
                  <div className="course-card__top">
                    <div className="row course-card__identity">
                      <span className="course-card__icon" style={{ backgroundColor: color }}>
                        <BookOpen size={20} />
                      </span>
                      <div className="course-card__heading">
                        <p className="course-card__eyebrow">Cours #{course.id}</p>
                        <h2 className="course-card__name">{course.title}</h2>
                      </div>
                    </div>
                    <div className="course-card__icon-actions">
                      <button
                        onClick={() => openEdit(course)}
                        aria-label={`Modifier ${course.title}`}
                        className="icon-button action-icon"
                      >
                        <Pencil size={16} />
                      </button>
                      <button
                        onClick={() => deleteCourse(course)}
                        disabled={courseDocuments.length > 0}
                        title={
                          courseDocuments.length
                            ? "Supprimez d’abord les documents de ce cours."
                            : "Supprimer le cours"
                        }
                        aria-label={`Supprimer ${course.title}`}
                        className="icon-button action-icon action-icon--danger"
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                  </div>
                  <p className="course-card__description">
                    {course.description || "Aucune description pour ce cours."}
                  </p>
                  <div className="course-card__counts">
                    <div className="course-card__count">
                      <strong>{courseDocuments.length}</strong>
                      <span>
                        <FileText size={12} /> Documents
                      </span>
                    </div>
                    <div className="course-card__count">
                      <strong>{indexedCount}</strong>
                      <span>Indexés</span>
                    </div>
                  </div>
                  <div className="course-card__actions">
                    <Link to="/documents" className="button button--secondary button--compact">
                      Voir les documents
                    </Link>
                    <Link to="/assistant" className="button button--teal button--compact">
                      Interroger le cours
                    </Link>
                    {courseDocuments.length > 0 && (
                      <Badge tone={indexedCount ? "teal" : "amber"}>
                        {indexedCount
                          ? `${indexedCount} indexé${indexedCount > 1 ? "s" : ""}`
                          : "À indexer"}
                      </Badge>
                    )}
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      ) : (
        <EmptyState
          icon={BookOpen}
          title={query ? "Aucun cours trouvé" : "Aucun cours pour le moment"}
          description={
            query
              ? "Essayez une autre recherche."
              : "Créez un espace pour commencer à organiser vos documents."
          }
          action={
            !query && (
              <Button variant="teal" onClick={openCreate}>
                <Plus size={16} />
                Créer un cours
              </Button>
            )
          }
        />
      )}

      <Modal
        open={modal?.type === "create" || modal?.type === "edit"}
        title={modal?.type === "edit" ? "Modifier le cours" : "Créer un cours"}
        onClose={() => setModal(null)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setModal(null)}>
              Annuler
            </Button>
            <Button variant="teal" type="submit" form="course-form" disabled={submitting}>
              {submitting ? "Enregistrement…" : modal?.type === "edit" ? "Enregistrer" : "Créer"}
            </Button>
          </>
        }
      >
        <form id="course-form" onSubmit={saveCourse} className="stack">
          {requestError && (
            <p role="alert" className="notice notice--error">
              {requestError}
            </p>
          )}
          <Field label="Nom du cours">
            <input
              className={inputClass}
              required
              maxLength={200}
              autoFocus
              value={form.title}
              onChange={(event) => setForm({ ...form, title: event.target.value })}
              placeholder="Ex. Bases de données"
            />
          </Field>
          <Field label="Description" hint="Facultative">
            <textarea
              className={`${inputClass} form-control--textarea`}
              value={form.description}
              onChange={(event) => setForm({ ...form, description: event.target.value })}
              placeholder="Quelques mots sur le cours…"
            />
          </Field>
        </form>
      </Modal>
    </div>
  );
}
