import { ApiError, apiEventStream, apiRequest } from "./api";

export function askCourse(token, courseId, query) {
  return apiRequest(`/courses/${courseId}/ask`, {
    method: "POST",
    token,
    body: { query, limit: 5 },
  });
}

export async function askCourseStream(token, courseId, query, onDelta) {
  let result;
  await apiEventStream(`/courses/${courseId}/ask/stream`, {
    method: "POST",
    token,
    body: { query, limit: 5 },
    onEvent(event) {
      if (event.type === "delta" && typeof event.text === "string") {
        onDelta(event.text);
      } else if (event.type === "complete") {
        result = event.response;
      } else if (event.type === "error") {
        throw new ApiError(event.detail || "La génération a échoué.", 502);
      } else {
        throw new ApiError("L'API a envoyé un événement de réponse inconnu.", 502);
      }
    },
  });
  if (!result) {
    throw new ApiError("Le flux s'est terminé sans réponse complète.", 502);
  }
  return result;
}
