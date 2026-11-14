import { apiRequest } from "./api";

export function askCourse(token, courseId, query) {
  return apiRequest(`/courses/${courseId}/ask`, {
    method: "POST",
    token,
    body: { query, limit: 5 },
  });
}
