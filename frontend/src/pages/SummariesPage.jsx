import { useEffect, useMemo, useState } from "react";
import { BookOpen, ChevronDown, Clipboard, FileText, NotebookPen, Sparkles } from "lucide-react";
import { useNavigate } from "react-router";
import { useAuth } from "../context/AuthContext";
import { useStudyData } from "../context/StudyDataContext";
import { studyGuideApi } from "../services/studyGuideApi";
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

const kindLabels = {
  short: "Résumé court",
  detailed: "Résumé détaillé",
  sheet: "Fiche de révision",
};

const unitLabels = {
  page: "page",
  slide: "diapositive",
  paragraph: "paragraphe",
  line: "ligne",
};

function formatLocation(segment) {
  return `${unitLabels[segment.location_type] ?? segment.location_type} ${segment.location_number}`;
}

export default function SummariesPage() {
  const { token } = useAuth();
  const { courses, documents, loading, error } = useStudyData();
  const navigate = useNavigate();
  const [courseId, setCourseId] = useState("");
  const [documentId, setDocumentId] = useState("");
  const [kind, setKind] = useState("short");
  const [generated, setGenerated] = useState(null);
  const [generating, setGenerating] = useState(false);
  const [notice, setNotice] = useState("");
  const [requestError, setRequestError] = useState("");

  useEffect(() => {
    if (!courses.some((course) => String(course.id) === courseId)) {
      setCourseId(courses.length ? String(courses[0].id) : "");
    }
  }, [courses, courseId]);

  const courseDocuments = useMemo(
    () =>
      documents.filter(
        (document) => String(document.course_id) === courseId && document.status === "indexed",
      ),
    [documents, courseId],
  );
  const selectedDocument = courseDocuments.find((document) => String(document.id) === documentId);

  useEffect(() => {
    if (documentId && !courseDocuments.some((document) => String(document.id) === documentId)) {
      setDocumentId("");
    }
  }, [courseDocuments, documentId]);

  function changeCourse(value) {
    setCourseId(value);
    setDocumentId("");
    setGenerated(null);
    setNotice("");
    setRequestError("");
  }

  async function generate() {
    if (!selectedDocument || generating) return;
    setGenerating(true);
    setGenerated(null);
    setNotice("");
    setRequestError("");
    try {
      const result = await studyGuideApi.generate(token, selectedDocument.id, kind);
      setGenerated(result);
    } catch (generationError) {
      setRequestError(generationError.message);
    } finally {
      setGenerating(false);
    }
  }

  async function copyContent() {
    if (!generated) return;
    const sections = generated.sections.map((section) => `${section.title}\n${section.text}`);
    const flashcards = generated.flashcards.map(
      (card) => `Question : ${card.question}\nRéponse : ${card.answer}`,
    );
    const text = [generated.title, generated.intro, ...sections, ...flashcards].join("\n\n");
    try {
      await navigator.clipboard.writeText(text);
      setNotice("Le support a été copié.");
    } catch {
      setNotice("La copie n’est pas disponible dans ce navigateur.");
    }
  }

  if (loading) return <LoadingState label="Chargement de vos documents…" />;

  if (!courses.length) {
    return (
      <div>
        <PageHeader eyebrow="Vos supports de révision" title="Résumés et fiches" />
        {error ? (
          <div role="alert" className="notice notice--error">
            {error}
          </div>
        ) : (
          <EmptyState
            icon={BookOpen}
            title="Aucun cours disponible"
            description="Créez un cours et ajoutez-y un document pour générer un support de révision."
            action={
              <Button variant="secondary" onClick={() => navigate("/cours")}>
                Voir mes cours
              </Button>
            }
          />
        )}
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        eyebrow="Vos supports de révision"
        title="Résumés et fiches"
        description="Générez un résumé ou une fiche à partir d’un document indexé."
      />

      {(error || requestError || notice) && (
        <div
          role={requestError || error ? "alert" : "status"}
          className={`notice ${requestError || error ? "notice--error" : "notice--success"}`}
        >
          <span>{requestError || error || notice}</span>
        </div>
      )}

      <Card className="study-guide-form">
        <div className="study-guide-form__heading">
          <span className="study-guide-form__icon">
            <Sparkles size={20} />
          </span>
          <div>
            <h2>Créer un support</h2>
            <p>
              Le support s’appuie sur les passages indexés les plus pertinents du document choisi.
              Consultez les sources pour vérifier sa couverture.
            </p>
          </div>
        </div>
        <div className="study-guide-form__fields">
          <Field label="Cours">
            <select
              className={inputClass}
              value={courseId}
              onChange={(event) => changeCourse(event.target.value)}
            >
              {courses.map((course) => (
                <option key={course.id} value={course.id}>
                  {course.title}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Document indexé">
            <select
              className={inputClass}
              value={documentId}
              onChange={(event) => {
                setDocumentId(event.target.value);
                setGenerated(null);
                setRequestError("");
              }}
              disabled={!courseDocuments.length || generating}
            >
              <option value="">Choisir un document</option>
              {courseDocuments.map((document) => (
                <option key={document.id} value={document.id}>
                  {document.original_name}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Format">
            <select
              className={inputClass}
              value={kind}
              onChange={(event) => {
                setKind(event.target.value);
                setGenerated(null);
              }}
              disabled={generating}
            >
              <option value="short">Résumé court</option>
              <option value="detailed">Résumé détaillé</option>
              <option value="sheet">Fiche de révision</option>
            </select>
          </Field>
        </div>
        {!courseDocuments.length && (
          <p className="study-guide-form__empty">
            Aucun document indexé dans ce cours. Indexez un document depuis la page Documents.
          </p>
        )}
        <div className="study-guide-form__actions">
          <Button variant="teal" onClick={generate} disabled={!selectedDocument || generating}>
            <Sparkles size={17} />
            {generating ? "Génération…" : "Générer le support"}
          </Button>
          {selectedDocument && (
            <span className="muted small">Document : {selectedDocument.original_name}</span>
          )}
        </div>
      </Card>

      {generating && (
        <Card className="study-guide-loading">
          <LoadingState label="Génération du support à partir des sources…" />
        </Card>
      )}

      {generated && (
        <Card className="study-guide-result">
          <div className="study-guide-result__header">
            <div>
              <div className="study-guide-result__badges">
                <Badge tone="slate">{selectedDocument?.original_name}</Badge>
                <Badge tone="teal">{kindLabels[generated.kind]}</Badge>
              </div>
              <h2>{generated.title}</h2>
            </div>
            <Button variant="secondary" onClick={copyContent}>
              <Clipboard size={16} />
              Copier le support
            </Button>
          </div>
          <div className="study-guide-result__content">
            <p className="study-guide-result__intro">{generated.intro}</p>
            {!!generated.sections.length && (
              <div className="study-guide-result__sections">
                {generated.sections.map((section, index) => (
                  <section key={`${section.title}-${index}`} className="study-guide-section">
                    <div className="study-guide-section__heading">
                      <span>{index + 1}</span>
                      <h3>{section.title}</h3>
                    </div>
                    <p>{section.text}</p>
                  </section>
                ))}
              </div>
            )}
            {!!generated.flashcards.length && (
              <section className="study-guide-flashcards">
                <h3>Fiches de révision</h3>
                <p>Ouvrez une question pour afficher sa réponse.</p>
                <div className="study-guide-flashcards__list">
                  {generated.flashcards.map((card, index) => (
                    <details key={`${card.question}-${index}`} className="study-guide-flashcard">
                      <summary>{card.question}</summary>
                      <p>{card.answer}</p>
                    </details>
                  ))}
                </div>
              </section>
            )}
            {!!generated.citations.length && (
              <details className="citation-list study-guide-citations">
                <summary className="citation-list__title">
                  Sources ({generated.citations.length})
                  <ChevronDown className="citation-list__chevron" size={16} aria-hidden="true" />
                </summary>
                {generated.citations.map((citation) => (
                  <div key={citation.citation_id} className="citation">
                    <p className="citation__source">
                      <FileText size={14} />[{citation.citation_id}] {citation.document_name} ·{" "}
                      {formatLocation(citation.segment)}
                    </p>
                    <p className="citation__content">{citation.segment.content}</p>
                  </div>
                ))}
              </details>
            )}
          </div>
        </Card>
      )}
    </div>
  );
}
