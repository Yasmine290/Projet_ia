import { useEffect, useRef, useState } from "react";
import { Bot, FileText, LoaderCircle, Send, Sparkles, UserRound } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { useStudyData } from "../context/StudyDataContext";
import { askCourse } from "../services/assistantApi";
import { Badge, Button, Card, Field, inputClass, LoadingState, PageHeader } from "../components/ui";

const suggestions = [
  "Quels sont les points principaux de ce cours ?",
  "Explique-moi une notion importante avec un exemple.",
  "Quelles différences les documents présentent-ils ?",
];

function createMessageId() {
  return globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random()}`;
}

function formatLocation(segment) {
  const labels = {
    page: "page",
    slide: "diapositive",
    paragraph: "paragraphe",
    line: "ligne",
  };
  return `${labels[segment.location_type] ?? segment.location_type} ${segment.location_number}`;
}

export default function AssistantPage() {
  const { token } = useAuth();
  const { courses, documents, loading } = useStudyData();
  const [courseId, setCourseId] = useState("");
  const [message, setMessage] = useState("");
  const [messages, setMessages] = useState([]);
  const [requestError, setRequestError] = useState("");
  const [lastFailedQuery, setLastFailedQuery] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const endRef = useRef(null);
  const selectedCourse = courses.find((course) => String(course.id) === courseId);
  const indexedDocuments = documents.filter(
    (document) => document.course_id === selectedCourse?.id && document.status === "indexed",
  );

  useEffect(() => {
    if (!courses.some((course) => String(course.id) === courseId)) {
      setCourseId(courses.length ? String(courses[0].id) : "");
    }
  }, [courses, courseId]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, submitting]);

  async function sendQuestion(question = message) {
    const text = question.trim();
    if (!text || submitting || !selectedCourse) return;

    // Les échanges restent uniquement en mémoire ; l'API traite chaque question indépendamment.
    setMessages((current) => [...current, { id: createMessageId(), role: "user", text }]);
    setMessage("");
    setRequestError("");
    setLastFailedQuery("");
    setSubmitting(true);
    try {
      const response = await askCourse(token, selectedCourse.id, text);
      setMessages((current) => [
        ...current,
        {
          id: createMessageId(),
          role: "assistant",
          text: response.answer,
          citations: response.citations,
        },
      ]);
    } catch (error) {
      setRequestError(error.message);
      setLastFailedQuery(text);
    } finally {
      setSubmitting(false);
    }
  }

  function changeCourse(nextCourseId) {
    setCourseId(nextCourseId);
    setMessages([]);
    setRequestError("");
    setLastFailedQuery("");
  }

  if (loading) return <LoadingState label="Chargement de vos cours…" />;

  return (
    <div>
      <PageHeader
        eyebrow="Posez vos questions"
        title="Assistant intelligent"
        description="Les réponses s’appuient sur les passages indexés des documents du cours sélectionné."
      />
      <div className="assistant-grid">
        <Card className="assistant-card">
          <div className="assistant-card__header">
            <div className="row">
              <span className="assistant-card__brand">
                <Bot size={21} />
              </span>
              <div>
                <h2>StudyAI</h2>
                <p>Assistant connecté à l’API locale</p>
              </div>
            </div>
            <Badge tone={indexedDocuments.length ? "teal" : "amber"}>
              {indexedDocuments.length
                ? `${indexedDocuments.length} document${indexedDocuments.length === 1 ? "" : "s"} indexé${indexedDocuments.length === 1 ? "" : "s"}`
                : "Aucun document indexé"}
            </Badge>
          </div>

          <div className="assistant-card__messages" aria-live="polite">
            {!messages.length && (
              <div className="assistant-welcome">
                <Bot size={26} />
                <h3>Comment puis-je vous aider ?</h3>
                <p>
                  Choisissez un cours et posez une question. Les sources réelles apparaîtront sous
                  chaque réponse.
                </p>
              </div>
            )}
            {messages.map((entry) => (
              <div
                key={entry.id}
                className={`message ${entry.role === "user" ? "message--user" : ""}`}
              >
                <span className="message__avatar">
                  {entry.role === "user" ? <UserRound size={16} /> : <Bot size={17} />}
                </span>
                <div className="message__bubble">
                  <p className="message__text">{entry.text}</p>
                  {entry.citations?.length > 0 && (
                    <div className="citation-list">
                      <p className="citation-list__title">Sources</p>
                      {entry.citations.map((citation) => (
                        <div key={citation.citation_id} className="citation">
                          <p className="citation__source">
                            <FileText size={14} />[{citation.citation_id}] {citation.document_name}{" "}
                            · {formatLocation(citation.segment)}
                          </p>
                          <p className="citation__content">{citation.segment.content}</p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}
            {submitting && (
              <div className="message">
                <span className="message__avatar">
                  <Bot size={17} />
                </span>
                <div className="assistant-thinking">
                  <LoaderCircle size={16} />
                  StudyAI prépare une réponse…
                </div>
              </div>
            )}
            <div ref={endRef} />
          </div>

          {requestError && (
            <div role="alert" className="notice notice--error assistant-error">
              <p>{requestError}</p>
              {lastFailedQuery && (
                <button className="text-button" onClick={() => sendQuestion(lastFailedQuery)}>
                  Réessayer
                </button>
              )}
            </div>
          )}

          <form
            className="assistant-card__form"
            onSubmit={(event) => {
              event.preventDefault();
              sendQuestion();
            }}
          >
            <label className="visually-hidden" htmlFor="assistant-message">
              Votre question
            </label>
            <textarea
              id="assistant-message"
              rows={2}
              maxLength={2000}
              className={`${inputClass} form-control--textarea assistant-card__input`}
              value={message}
              onChange={(event) => setMessage(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  sendQuestion();
                }
              }}
              placeholder="Écrivez votre question…"
              disabled={!selectedCourse || submitting}
            />
            <Button
              type="submit"
              variant="teal"
              className="assistant-card__send"
              disabled={!message.trim() || !selectedCourse || submitting}
              aria-label="Envoyer la question"
            >
              <Send size={17} />
              <span>Envoyer</span>
            </Button>
          </form>
          <p className="assistant-card__hint">
            Entrée pour envoyer · Maj + Entrée pour une nouvelle ligne · Les échanges ne sont pas
            conservés après fermeture de la page.
          </p>
        </Card>

        <aside className="assistant-side">
          <Card className="assistant-side__card">
            <h3>Contexte de la question</h3>
            <Field label="Cours">
              <select
                className={inputClass}
                value={courseId}
                onChange={(event) => changeCourse(event.target.value)}
                disabled={!courses.length || submitting}
              >
                <option value="">Choisir un cours</option>
                {courses.map((course) => (
                  <option key={course.id} value={course.id}>
                    {course.title}
                  </option>
                ))}
              </select>
            </Field>
            <p className="assistant-context">
              La recherche porte sur tous les documents indexés du cours. Chaque question est
              traitée indépendamment ; l’historique affiché reste temporaire.
            </p>
            {!indexedDocuments.length && selectedCourse && (
              <p className="assistant-warning">
                Indexez au moins un document de ce cours depuis la page Documents.
              </p>
            )}
          </Card>
          <Card className="assistant-side__card">
            <div className="row assistant-side__title">
              <Sparkles size={17} />
              <h3>Suggestions</h3>
            </div>
            <div className="suggestion-list">
              {suggestions.map((suggestion) => (
                <button
                  key={suggestion}
                  onClick={() => sendQuestion(suggestion)}
                  disabled={!selectedCourse || submitting}
                  className="suggestion-button"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </Card>
        </aside>
      </div>
    </div>
  );
}
