import { useEffect, useMemo, useRef, useState } from "react";
import { BookOpen, FileText, FileUp, Info, Search, Trash2 } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { useStudyData } from "../context/StudyDataContext";
import { documentsApi } from "../services/documentsApi";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  Field,
  inputClass,
  LoadingState,
  PageHeader,
} from "../components/ui";

const supportedExtensions = new Set(["pdf", "docx", "pptx", "txt", "doc", "ppt"]);
const statusLabels = {
  pending_indexing: "À indexer",
  indexed: "Indexé",
  ocr_required: "OCR requis",
  no_text: "Aucun texte",
};
const unitLabels = {
  page: "page",
  slide: "diapositive",
  paragraph: "paragraphe",
  line: "ligne",
};

function formatCreatedAt(value) {
  if (!value) return "Date inconnue";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "Date inconnue"
    : new Intl.DateTimeFormat("fr-CA", { dateStyle: "medium" }).format(date);
}

export default function DocumentsPage() {
  const { token } = useAuth();
  const { courses, documents, loading, error, refresh } = useStudyData();
  const [courseFilter, setCourseFilter] = useState("all");
  const [selectedCourse, setSelectedCourse] = useState("");
  const [query, setQuery] = useState("");
  const [selectedFile, setSelectedFile] = useState(null);
  const [notice, setNotice] = useState("");
  const [requestError, setRequestError] = useState("");
  const [busyDocument, setBusyDocument] = useState(null);
  const [uploading, setUploading] = useState(false);
  const inputRef = useRef(null);

  useEffect(() => {
    const selectedCourseExists = courses.some((course) => String(course.id) === selectedCourse);
    if (!selectedCourseExists) {
      setSelectedCourse(courses.length ? String(courses[0].id) : "");
    }
  }, [courses, selectedCourse]);

  const visibleDocuments = useMemo(
    () =>
      documents.filter((document) => {
        const matchesCourse = courseFilter === "all" || String(document.course_id) === courseFilter;
        const matchesText = document.original_name.toLowerCase().includes(query.toLowerCase());
        return matchesCourse && matchesText;
      }),
    [documents, courseFilter, query],
  );

  function chooseFile(event) {
    const file = event.target.files?.[0] ?? null;
    setNotice("");
    setRequestError("");
    if (!file) return;
    const extension = file.name.split(".").pop()?.toLowerCase();
    // Refuser ici les formats que l'API ne sait pas importer évite un envoi voué à échouer.
    if (!extension || !supportedExtensions.has(extension)) {
      setSelectedFile(null);
      setRequestError("Format non pris en charge. Choisissez PDF, DOCX, PPTX, TXT, DOC ou PPT.");
      event.target.value = "";
      return;
    }
    setSelectedFile(file);
  }

  async function uploadFile(event) {
    event.preventDefault();
    if (!selectedFile || !selectedCourse) {
      setRequestError("Choisissez un fichier et le cours auquel l'associer.");
      return;
    }

    setRequestError("");
    setNotice("");
    setUploading(true);
    try {
      await documentsApi.upload(token, Number(selectedCourse), selectedFile);
      setSelectedFile(null);
      if (inputRef.current) inputRef.current.value = "";
      setNotice("Document importé. Indexez-le pour pouvoir interroger son contenu.");
      refresh();
    } catch (requestError) {
      setRequestError(requestError.message);
    } finally {
      setUploading(false);
    }
  }

  async function indexDocument(document) {
    setRequestError("");
    setNotice("");
    setBusyDocument(document.id);
    try {
      await documentsApi.index(token, document.id);
      setNotice(`« ${document.original_name} » est indexé et prêt pour l’assistant.`);
      refresh();
    } catch (requestError) {
      setRequestError(requestError.message);
    } finally {
      setBusyDocument(null);
    }
  }

  async function deleteDocument(document) {
    if (!window.confirm(`Supprimer « ${document.original_name} » et son index ?`)) return;
    setRequestError("");
    setNotice("");
    setBusyDocument(document.id);
    try {
      await documentsApi.remove(token, document.id);
      setNotice(`« ${document.original_name} » a été supprimé.`);
      refresh();
    } catch (requestError) {
      setRequestError(requestError.message);
    } finally {
      setBusyDocument(null);
    }
  }

  if (loading) return <LoadingState label="Chargement de vos documents…" />;

  return (
    <div>
      <PageHeader
        eyebrow="Bibliothèque pédagogique"
        title="Documents"
        description="Importez vos supports, puis indexez-les pour les utiliser avec l’assistant."
      />

      {(error || requestError || notice) && (
        <div
          role={requestError || error ? "alert" : "status"}
          className={`notice ${
            requestError || error ? "notice--error" : "notice--success"
          } row row--between`}
        >
          <span>{requestError || error || notice}</span>
          {error && (
            <Button variant="secondary" onClick={refresh}>
              Réessayer
            </Button>
          )}
        </div>
      )}

      <Card className="document-upload">
        <div>
          <div className="row document-upload__heading">
            <span className="document-upload__icon">
              <FileUp size={20} />
            </span>
            <h2>Importer un document</h2>
          </div>
          <p className="document-upload__copy">
            Les fichiers sont envoyés à votre backend local. Les formats PDF, DOCX, PPTX, TXT, DOC
            et PPT sont acceptés.
          </p>
          <p className="document-upload__info">
            <Info size={16} />
            <span>
              L’indexation est une étape distincte. Un document non indexé n’est pas utilisé par
              l’assistant.
            </span>
          </p>
        </div>
        <form className="document-upload__form" onSubmit={uploadFile}>
          <Field label="Fichier">
            <input
              ref={inputRef}
              type="file"
              accept=".pdf,.docx,.pptx,.txt,.doc,.ppt,application/pdf,text/plain"
              onChange={chooseFile}
              className="form-control file-control"
              disabled={!courses.length || uploading}
            />
            {selectedFile && (
              <span className="field__hint document-upload__filename">
                Sélectionné : {selectedFile.name}
              </span>
            )}
          </Field>
          <div className="document-upload__row">
            <Field label="Associer au cours">
              <select
                className={inputClass}
                value={selectedCourse}
                onChange={(event) => setSelectedCourse(event.target.value)}
                disabled={!courses.length || uploading}
                required
              >
                <option value="">Choisir un cours</option>
                {courses.map((course) => (
                  <option value={course.id} key={course.id}>
                    {course.title}
                  </option>
                ))}
              </select>
            </Field>
            <Button
              variant="teal"
              type="submit"
              disabled={!selectedFile || !selectedCourse || uploading}
            >
              {uploading ? "Importation…" : "Importer"}
            </Button>
          </div>
          {!courses.length && (
            <p className="muted small">Créez d’abord un cours pour pouvoir importer un document.</p>
          )}
        </form>
      </Card>

      <div className="documents-toolbar">
        <div>
          <h2 className="toolbar-title">
            Vos documents <span className="toolbar-count">({visibleDocuments.length})</span>
          </h2>
          <p className="toolbar-description">Ressources réellement enregistrées par l’API</p>
        </div>
        <div className="documents-toolbar__filters">
          <label className="search-control">
            <Search size={17} />
            <input
              className="form-control"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Rechercher un document…"
              aria-label="Rechercher un document"
            />
          </label>
          <select
            className="form-control documents-toolbar__course-filter"
            value={courseFilter}
            onChange={(event) => setCourseFilter(event.target.value)}
            aria-label="Filtrer par cours"
          >
            <option value="all">Tous les cours</option>
            {courses.map((course) => (
              <option key={course.id} value={course.id}>
                {course.title}
              </option>
            ))}
          </select>
        </div>
      </div>

      {visibleDocuments.length ? (
        <Card className="document-list">
          <div className="document-list__header">
            <span>Document</span>
            <span>Cours associé</span>
            <span>Importé le</span>
            <span>Statut et actions</span>
          </div>
          <ul className="document-list__items">
            {visibleDocuments.map((document) => {
              const course = courses.find((item) => item.id === document.course_id);
              const tone =
                document.status === "indexed"
                  ? "teal"
                  : document.status === "pending_indexing"
                    ? "amber"
                    : "red";
              return (
                <li key={document.id} className="document-row">
                  <div className="document-row__name">
                    <span className="document-row__icon">
                      <FileText size={20} />
                    </span>
                    <div className="document-row__details">
                      <p className="document-row__title">{document.original_name}</p>
                      <span className="document-row__meta">
                        {document.unit_count === null
                          ? "Nombre d’unités inconnu"
                          : `${document.unit_count} ${unitLabels[document.unit_type] ?? "unités"}`}
                      </span>
                    </div>
                  </div>
                  <div className="document-row__course">
                    <BookOpen size={15} />
                    {course?.title ?? "Cours introuvable"}
                  </div>
                  <div className="document-row__date">{formatCreatedAt(document.created_at)}</div>
                  <div className="document-row__actions">
                    <Badge tone={tone}>{statusLabels[document.status] ?? document.status}</Badge>
                    {document.status === "pending_indexing" && (
                      <Button
                        variant="secondary"
                        className="button--compact"
                        disabled={busyDocument === document.id}
                        onClick={() => indexDocument(document)}
                      >
                        {busyDocument === document.id ? "Indexation…" : "Indexer"}
                      </Button>
                    )}
                    <button
                      title="Supprimer le document"
                      aria-label={`Supprimer ${document.original_name}`}
                      disabled={busyDocument === document.id}
                      onClick={() => deleteDocument(document)}
                      className="icon-button action-icon action-icon--danger document-row__delete"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                </li>
              );
            })}
          </ul>
        </Card>
      ) : (
        <EmptyState
          icon={FileText}
          title={documents.length ? "Aucun document trouvé" : "Votre bibliothèque est vide"}
          description={
            documents.length
              ? "Modifiez vos filtres ou votre recherche."
              : "Importez un document pour le conserver dans votre compte."
          }
        />
      )}
    </div>
  );
}
